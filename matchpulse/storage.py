"""Single-writer append-only storage. Publication shares the ingestion transaction."""
from __future__ import annotations
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
from typing import Iterator
from .contracts import ContractError, Envelope, canonical, instant

SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources(
 id TEXT PRIMARY KEY, mode TEXT NOT NULL, name TEXT NOT NULL, terms_url TEXT NOT NULL,
 redistribution INTEGER NOT NULL, freshness_seconds REAL, acquired_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS persons(id TEXT PRIMARY KEY,name TEXT NOT NULL,birth_date TEXT,country TEXT);
CREATE TABLE IF NOT EXISTS aliases(
 provider TEXT NOT NULL,vendor_id TEXT NOT NULL,person_id TEXT NOT NULL REFERENCES persons(id),
 valid_from TEXT NOT NULL,valid_to TEXT,known_at TEXT NOT NULL,
 PRIMARY KEY(provider,vendor_id,known_at));
CREATE TABLE IF NOT EXISTS identity_audit(
 seq INTEGER PRIMARY KEY, action TEXT NOT NULL,body TEXT NOT NULL,known_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS registrations(
 id TEXT PRIMARY KEY,person_id TEXT NOT NULL REFERENCES persons(id),team_id TEXT NOT NULL,
 valid_from TEXT NOT NULL,valid_to TEXT,known_at TEXT NOT NULL,kind TEXT NOT NULL,
 source_id TEXT NOT NULL,confidence REAL NOT NULL);
CREATE TABLE IF NOT EXISTS fixtures(id TEXT PRIMARY KEY,body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS journal(
 seq INTEGER PRIMARY KEY AUTOINCREMENT,match_id TEXT NOT NULL REFERENCES fixtures(id),
 provider TEXT NOT NULL,event_id TEXT NOT NULL,revision INTEGER NOT NULL,
 occurred_at TEXT NOT NULL,published_at TEXT,received_at TEXT NOT NULL,
 fact_hash TEXT NOT NULL,body TEXT NOT NULL,
 UNIQUE(match_id,provider,event_id,revision));
CREATE INDEX IF NOT EXISTS journal_match ON journal(match_id,seq);
CREATE TABLE IF NOT EXISTS snapshots(
 match_id TEXT NOT NULL,version INTEGER NOT NULL,journal_seq INTEGER NOT NULL,
 body TEXT NOT NULL,PRIMARY KEY(match_id,version));
CREATE TABLE IF NOT EXISTS stream(
 seq INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,match_id TEXT,
 body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS estimates(
 seq INTEGER PRIMARY KEY AUTOINCREMENT,person_id TEXT NOT NULL,match_id TEXT NOT NULL,
 version INTEGER NOT NULL,known_at TEXT NOT NULL,model_id TEXT NOT NULL,body TEXT NOT NULL,
 UNIQUE(person_id,match_id,version,model_id));
CREATE TABLE IF NOT EXISTS deals(id TEXT PRIMARY KEY,person_id TEXT NOT NULL,known_at TEXT NOT NULL,body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS context_assertions(
 seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT NOT NULL,revision INTEGER NOT NULL,
 person_id TEXT NOT NULL REFERENCES persons(id),kind TEXT NOT NULL,known_at TEXT NOT NULL,
 valid_from TEXT NOT NULL,valid_to TEXT,source_id TEXT NOT NULL REFERENCES sources(id),
 body TEXT NOT NULL,UNIQUE(id,revision));
CREATE INDEX IF NOT EXISTS context_person_time ON context_assertions(person_id,known_at,revision);
CREATE INDEX IF NOT EXISTS estimate_person_time ON estimates(person_id,known_at,seq);
CREATE INDEX IF NOT EXISTS deal_person_time ON deals(person_id,known_at);
CREATE TABLE IF NOT EXISTS model_registry(id TEXT PRIMARY KEY,body TEXT NOT NULL);
"""


class Store:
    def __init__(self, path: str | Path, max_bytes: int = 512_000_000):
        self.path = str(path)
        if self.path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2):
            raise ContractError(f"unsupported schema version {version}")
        page_size=self.db.execute("PRAGMA page_size").fetchone()[0]
        if type(max_bytes) is not int or max_bytes < page_size*32:
            self.db.close()
            raise ContractError("database budget is too small for schema")
        pages=max_bytes//page_size
        actual=self.db.execute(f"PRAGMA max_page_count={pages}").fetchone()[0]
        if actual>pages:
            self.db.close()
            raise ContractError("existing database exceeds configured storage cap")
        self.db.executescript(SCHEMA)
        self.db.execute("PRAGMA user_version=2")
        for table in ("journal", "snapshots", "stream", "estimates", "identity_audit", "aliases", "registrations", "deals", "context_assertions"):
            for action in ("UPDATE", "DELETE"):
                self.db.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'append-only table'); END")

    def close(self) -> None:
        self.db.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        started=time.perf_counter()
        self.last_transaction=dict(begin_ms=0.0,body_ms=0.0,commit_ms=0.0,rollback_ms=0.0,status='pending')
        self.db.execute("BEGIN IMMEDIATE")
        body_started=time.perf_counter();self.last_transaction['begin_ms']=(body_started-started)*1000
        try:
            yield
            commit_started=time.perf_counter();self.last_transaction['body_ms']=(commit_started-body_started)*1000
            self.db.execute("COMMIT")
            self.last_transaction.update(commit_ms=(time.perf_counter()-commit_started)*1000,status='committed')
        except BaseException:
            rollback_started=time.perf_counter()
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            self.last_transaction.update(rollback_ms=(time.perf_counter()-rollback_started)*1000,status='rolled-back')
            raise

    def source(self, source_id: str) -> dict:
        row = self.db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
        if row is None:
            raise ContractError("source license is not registered")
        return dict(row)

    def fixture(self, match_id: str) -> dict:
        row = self.db.execute("SELECT body FROM fixtures WHERE id=?", (match_id,)).fetchone()
        if row is None:
            raise ContractError("unknown fixture")
        return json.loads(row[0])

    def append(self, event: Envelope) -> tuple[int, bool]:
        source = self.source(event.license_id)
        if event.mode != source["mode"]:
            raise ContractError("source mode mismatch")
        if event.mode == "live" and (not source["redistribution"] or source["freshness_seconds"] is None):
            raise ContractError("live source needs redistribution rights and freshness SLO")
        row = self.db.execute("SELECT seq,fact_hash FROM journal WHERE match_id=? AND provider=? AND event_id=? AND revision=?",
            (event.match_id, event.provider, event.event_id, event.revision)).fetchone()
        if row:
            if row["fact_hash"] != event.fact_hash():
                raise ContractError("revision collision: same key, different facts")
            return row["seq"], False
        fixture = self.fixture(event.match_id)
        if event.mode != fixture["mode"]:
            raise ContractError("fixture mode mismatch")
        if event.team_id and event.team_id not in {fixture["home_id"], fixture["away_id"]}:
            raise ContractError("event team outside fixture")
        if event.player_id and not self.db.execute("SELECT 1 FROM persons WHERE id=?", (event.player_id,)).fetchone():
            raise ContractError("unknown person, resolve identity before ingest")
        # Receipt is the service's logical clock. A provider's clock is never substituted.
        previous = self.db.execute("SELECT received_at FROM journal ORDER BY seq DESC LIMIT 1").fetchone()
        if previous and event.received_at < previous[0]:
            raise ContractError("receipt clock regressed")
        cur = self.db.execute("INSERT INTO journal(match_id,provider,event_id,revision,occurred_at,published_at,received_at,fact_hash,body) VALUES(?,?,?,?,?,?,?,?,?)",
            (event.match_id, event.provider, event.event_id, event.revision, event.occurred_at,
             event.published_at, event.received_at, event.fact_hash(), canonical(event.wire())))
        return cur.lastrowid, True

    def events(self, match_id: str, cutoff: str | None = None, journal_seq: int | None = None) -> list[Envelope]:
        query = "SELECT body FROM journal WHERE match_id=?"
        args: list = [match_id]
        if cutoff:
            query += " AND received_at<=?"
            args.append(instant(cutoff))
        if journal_seq is not None:
            query += " AND seq<=?"
            args.append(journal_seq)
        return [Envelope.parse(json.loads(r[0])) for r in self.db.execute(query + " ORDER BY seq", args)]

    def latest(self, match_id: str) -> dict | None:
        row = self.db.execute("SELECT body FROM snapshots WHERE match_id=? ORDER BY version DESC LIMIT 1", (match_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def publish(self, kind: str, body: dict, match_id: str | None = None) -> int:
        return self.db.execute("INSERT INTO stream(kind,match_id,body) VALUES(?,?,?)", (kind, match_id, canonical(body))).lastrowid

    def stream(self, after: int = 0, limit: int = 256) -> list[dict]:
        if after < 0 or not 1 <= limit <= 1000:
            raise ContractError("invalid stream range")
        return [{"seq": r["seq"], "kind": r["kind"], "match_id": r["match_id"], "data": json.loads(r["body"])}
                for r in self.db.execute("SELECT * FROM stream WHERE seq>? ORDER BY seq LIMIT ?", (after, limit))]
