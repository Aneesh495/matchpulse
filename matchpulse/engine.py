"""Domain transaction boundary: journal, derived versions, and outbox commit together."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import time
from .contracts import ContractError, Envelope, canonical, identifier, instant
from .identity import Identity
from .context import ContextLedger
from .ratings import RatingReducer
from .storage import Store
from .valuation import Deal, diagnostic_estimate


class Engine:
    def __init__(self, store: Store):
        self.s = store
        self.identity = Identity(store)
        self.context = ContextLedger(store)

    def seed(self, packet: dict, publish_context: bool = False) -> dict:
        context_inserted = 0
        with self.s.transaction():
            for source in packet.get("sources", []):
                existing=self.s.db.execute("SELECT * FROM sources WHERE id=?", (source["id"],)).fetchone()
                values=(source["id"],source["mode"],source["name"],source["terms_url"],int(source["redistribution"]),source.get("freshness_seconds"),instant(source["acquired_at"]))
                if existing and tuple(existing) != values:
                    raise ContractError("source terms collision")
                self.s.db.execute("INSERT OR IGNORE INTO sources VALUES(?,?,?,?,?,?,?)",values)
            for fixture in packet.get("fixtures", []):
                identifier(fixture["id"])
                for p in fixture["players"]:
                    self.identity.add_person(p)
                existing=self.s.db.execute("SELECT body FROM fixtures WHERE id=?",(fixture["id"],)).fetchone()
                if existing and existing[0] != canonical(fixture):
                    raise ContractError("fixture identifier collision")
                self.s.db.execute("INSERT OR IGNORE INTO fixtures VALUES(?,?)",(fixture["id"],canonical(fixture)))
            for person in packet.get("persons", []):
                self.identity.add_person(person)
            for fact in packet.get("context", []):
                inserted = self.context.append(fact)
                context_inserted += inserted
                if inserted and publish_context:
                    self.s.publish("context", {"person_id": fact["person_id"], "fact_id": fact["id"], "revision": fact["revision"]})
        return {"fixtures": len(packet.get("fixtures", [])), "context_inserted": context_inserted}

    def ingest(self, raw: dict, failpoint: str | None = None) -> dict:
        start=time.perf_counter()
        event=Envelope.parse(raw)
        with self.s.transaction():
            append_started=time.perf_counter()
            seq, inserted=self.s.append(event)
            append_ms=(time.perf_counter()-append_started)*1000
            if not inserted:
                return {"duplicate":True,"journal_seq":seq,"snapshot":self.s.latest(event.match_id)}
            if failpoint == "after-journal":
                raise RuntimeError("injected failure after journal append")
            read_started=time.perf_counter()
            fixture=self.s.fixture(event.match_id)
            events=self.s.events(event.match_id)
            if len(events)>50000:
                raise ContractError("match journal capacity exceeded")
            read_ms=(time.perf_counter()-read_started)*1000
            reduce_started=time.perf_counter()
            current=RatingReducer(fixture).run(events)
            reduce_ms=(time.perf_counter()-reduce_started)*1000
            previous=self.s.latest(event.match_id)
            version=1 if previous is None else previous["version"]+1
            current.update(version=version,journal_seq=seq)
            previous_players={p["id"]:p for p in previous["players"]} if previous else {}
            deltas=[]
            for p in current["players"]:
                old=previous_players.get(p["id"],{})
                p["delta"]=round(p["rating"]-old["rating"],4) if p["rating"] is not None and old.get("rating") is not None else None
                if p != old:
                    deltas.append(p)
            self.s.db.execute("INSERT INTO snapshots VALUES(?,?,?,?)",(event.match_id,version,seq,canonical(current)))
            corrected=event.revision>1 or event.kind=="retract" or (previous and event.clock < max((e.clock for e in events[:-1]),default=event.clock))
            if corrected:
                self.s.publish("invalidation",dict(match_id=event.match_id,prior_version=version-1,new_version=version,event_id=event.event_id,reason=event.payload.get("reason","revision or late arrival")),event.match_id)
            stream_seq=self.s.publish("snapshot",current,event.match_id)
            estimates=[]
            if current["status"]=="finished":
                persons={p["id"]:p for p in fixture["players"]}
                for p in current["players"]:
                    if p["status"]=="nonparticipant":
                        continue
                    row=self.s.db.execute("SELECT body FROM estimates WHERE person_id=? ORDER BY seq DESC LIMIT 1",(p["id"],)).fetchone()
                    prev=json.loads(row[0]) if row else None
                    estimate=diagnostic_estimate(persons[p["id"]],p,prev,current)
                    estimate["version"]=version
                    self.s.db.execute("INSERT INTO estimates(person_id,match_id,version,known_at,model_id,body) VALUES(?,?,?,?,?,?)",(p["id"],event.match_id,version,current["known_at"],estimate["model_id"],canonical(estimate)))
                    estimates.append(estimate)
                stream_seq=self.s.publish("ticker",dict(match_id=event.match_id,version=version,estimates=estimates),event.match_id)
            elif previous and previous["status"]=="finished":
                for p in current["players"]:
                    row=self.s.db.execute("SELECT body FROM estimates WHERE person_id=? AND match_id=? ORDER BY seq DESC LIMIT 1",(p["id"],event.match_id)).fetchone()
                    if not row:
                        continue
                    estimate=json.loads(row[0])
                    estimate.update(version=version,source_version=version,known_at=current["known_at"],status="unavailable",median=None,interval=None,delta=None,move_probability=None,reason="Match completion retracted or interrupted",attribution=[])
                    self.s.db.execute("INSERT INTO estimates(person_id,match_id,version,known_at,model_id,body) VALUES(?,?,?,?,?,?)",(p["id"],event.match_id,version,current["known_at"],estimate["model_id"],canonical(estimate)))
                    estimates.append(estimate)
                stream_seq=self.s.publish("ticker-retraction",dict(match_id=event.match_id,version=version,estimates=estimates),event.match_id)
            if failpoint=="before-commit":
                raise RuntimeError("injected failure before commit")
        return dict(duplicate=False,journal_seq=seq,stream_seq=stream_seq,version=version,
            corrected=bool(corrected),processing_ms=(time.perf_counter()-start)*1000,snapshot=current,
            timing={**self.s.last_transaction,"append_ms":append_ms,"journal_read_ms":read_ms,"reduce_ms":reduce_ms})

    def match(self, match_id: str, version: int | None = None, as_of: str | None = None) -> dict:
        if version is not None:
            row=self.s.db.execute("SELECT body FROM snapshots WHERE match_id=? AND version=?",(match_id,version)).fetchone()
            if row is None:
                raise ContractError("unknown snapshot version")
            return json.loads(row[0])
        if as_of:
            result=RatingReducer(self.s.fixture(match_id)).run(self.s.events(match_id,as_of))
            result["version"]=None
            result["view"]="as-known"
            return result
        latest=self.s.latest(match_id)
        return latest or {**RatingReducer(self.s.fixture(match_id)).run([]),"version":0}

    def matches(self) -> list[dict]:
        return [self.match(r[0]) for r in self.s.db.execute("SELECT id FROM fixtures ORDER BY id")]

    def knowledge_clock(self) -> str:
        clocks = [r[0] for r in self.s.db.execute("SELECT MAX(received_at) FROM journal UNION ALL SELECT MAX(known_at) FROM deals UNION ALL SELECT MAX(known_at) FROM context_assertions UNION ALL SELECT MAX(acquired_at) FROM sources") if r[0]]
        return max(map(instant, clocks), default="1970-01-01T00:00:00.000000+00:00")

    @staticmethod
    def freshness(estimate: dict, clock: str) -> dict:
        age = max(0.0, (datetime.fromisoformat(instant(clock)) - datetime.fromisoformat(instant(estimate["known_at"]))).total_seconds())
        state = "unavailable" if estimate["median"] is None else "historical" if estimate["mode"] in {"synthetic", "archive"} else "stale" if age > 7*86400 else "fresh"
        return dict(state=state, age_seconds=age, evaluated_at=instant(clock), threshold_seconds=7*86400,
            policy="Declared seven-day display policy; not a calibrated trading signal")

    def ticker(self, cutoff: str | None = None, evaluated_at: str | None = None) -> list[dict]:
        query="SELECT * FROM estimates"
        args=[]
        if cutoff:
            query+=" WHERE known_at<=?";args.append(instant(cutoff))
        results={}
        for r in self.s.db.execute(query+" ORDER BY seq DESC",args):
            results.setdefault(r["person_id"],json.loads(r["body"]))
        clock = instant(evaluated_at or cutoff or self.knowledge_clock())
        for p,result in results.items():
            deals=self.s.db.execute("SELECT body FROM deals WHERE person_id=?"+(" AND known_at<=?" if cutoff else "")+" ORDER BY known_at",(p,instant(cutoff)) if cutoff else (p,))
            result["transactions"]=[json.loads(d[0]) for d in deals]
            result["freshness"] = self.freshness(result, clock)
        return list(results.values())

    def history(self, person_id: str, cutoff: str | None = None, valid_at: str | None = None) -> dict:
        identifier(person_id)
        args = [person_id]
        condition = ""
        if cutoff:
            condition = " AND known_at<=?"; args.append(instant(cutoff))
        estimates = [json.loads(r[0]) for r in self.s.db.execute("SELECT body FROM estimates WHERE person_id=?"+condition+" ORDER BY seq", args)]
        transactions = [json.loads(r[0]) for r in self.s.db.execute("SELECT body FROM deals WHERE person_id=?"+condition+" ORDER BY known_at",args)]
        clock = instant(cutoff or self.knowledge_clock())
        for estimate in estimates:
            estimate["freshness"] = self.freshness(estimate, clock)
        return dict(person_id=person_id, as_of=cutoff, estimates=estimates, transactions=transactions,
            context=self.context.view(person_id, valid_at or clock, clock))

    def compare(self, person_ids: list[str], cutoff: str | None = None) -> dict:
        if not isinstance(person_ids, list) or not 1 <= len(person_ids) <= 3 or len(set(person_ids)) != len(person_ids):
            raise ContractError("comparison requires one to three distinct people")
        return dict(as_of=cutoff, players=[self.history(p, cutoff) for p in person_ids])

    def append_context(self, raw: dict) -> dict:
        with self.s.transaction():
            inserted = self.context.append(raw)
            seq = self.s.publish("context", {"person_id": raw["person_id"], "fact_id": raw["id"], "revision": raw["revision"]}) if inserted else None
        return dict(duplicate=not inserted, seq=seq)

    def deal(self, raw: dict) -> dict:
        d=Deal.parse(raw)
        source = self.s.source(d.source_id)
        if source["mode"] != d.mode:
            raise ContractError("transaction source mode mismatch")
        if not self.s.db.execute("SELECT 1 FROM persons WHERE id=?",(d.person_id,)).fetchone():
            raise ContractError("deal needs canonical person")
        with self.s.transaction():
            old=self.s.db.execute("SELECT body FROM deals WHERE id=?",(d.id,)).fetchone()
            if old:
                if old[0]!=canonical(d.wire()):
                    raise ContractError("deal collision")
                return {"duplicate":True}
            self.s.db.execute("INSERT INTO deals VALUES(?,?,?,?)",(d.id,d.person_id,instant(d.known_at),canonical(d.wire())))
            seq=self.s.publish("transaction",d.wire())
        return {"duplicate":False,"seq":seq}

    def coverage(self) -> dict:
        sources=[dict(r) for r in self.s.db.execute("SELECT * FROM sources")]
        fixtures=[json.loads(r[0]) for r in self.s.db.execute("SELECT body FROM fixtures")]
        actual=[f for f in fixtures if f["mode"]!="synthetic"]
        return dict(scope="Declared local demonstration slice",europe_complete=False,
            denominators={"federations":55,"federation_source":"UEFA member association target, reconciliation unverified", "registered_divisions":None,"registered_players":None},
            fixtures=len(fixtures),actual_fixtures=len(actual),sources=sources,
            competitions=sorted({f.get("competition","unknown") for f in fixtures}),
            missing=["Europe-wide division and roster reconciliation","licensed live integration","tracking and physical load","validated transaction model"],
            live_gate="blocked",rating_model="uncalibrated baseline",fee_model="synthetic diagnostics only")

    def snapshot(self) -> dict:
        seq=self.s.db.execute("SELECT COALESCE(MAX(seq),0) FROM stream").fetchone()[0]
        return dict(seq=seq,matches=self.matches(),ticker=self.ticker(),coverage=self.coverage())
