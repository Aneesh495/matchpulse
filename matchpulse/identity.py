"""Names are candidate keys, never proof that two people are the same person."""
from __future__ import annotations
from datetime import date
import json
import re
import unicodedata
from .contracts import ContractError, canonical, digest, finite, identifier, instant
from .storage import Store


def candidate_key(name: str, birth_date: str | None, country: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", name).casefold()
    normalized = " ".join(re.findall(r"[^\W_]+", normalized, re.UNICODE))
    return digest([normalized, birth_date, country])[:24]


class Identity:
    def __init__(self, store: Store):
        self.s = store

    def add_person(self, person: dict) -> str:
        pid = identifier(person["id"])
        name = person.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ContractError("person needs a bounded name")
        birth = person.get("birth_date")
        if birth:
            date.fromisoformat(birth)
        current = self.s.db.execute("SELECT * FROM persons WHERE id=?", (pid,)).fetchone()
        values = (pid, name, birth, person.get("country"))
        if current:
            if tuple(current) != values:
                raise ContractError("person identifier collision")
        else:
            self.s.db.execute("INSERT INTO persons VALUES(?,?,?,?)", values)
        return candidate_key(name, birth, person.get("country"))

    def resolve(self, provider: str, vendor_id: str, valid_at: str, known_at: str) -> str | None:
        valid, known = instant(valid_at), instant(known_at)
        rows = self.s.db.execute("SELECT * FROM aliases WHERE provider=? AND vendor_id=? AND known_at<=? ORDER BY known_at DESC", (provider, vendor_id, known))
        # The newest assertion is authoritative for its valid interval only.
        for row in rows:
            if row["valid_from"] <= valid and (row["valid_to"] is None or valid < row["valid_to"]):
                return row["person_id"]
        return None

    def bind(self, provider: str, vendor_id: str, person_id: str, valid_from: str,
             known_at: str, reason: str, valid_to: str | None = None, action: str = "bind") -> None:
        for value in (provider, vendor_id, person_id):
            identifier(value)
        start, known = instant(valid_from), instant(known_at)
        end = instant(valid_to) if valid_to else None
        if end and end <= start:
            raise ContractError("empty identity interval")
        if not reason.strip() or action not in {"bind", "merge", "split"}:
            raise ContractError("audited identity reason and action required")
        old = self.resolve(provider, vendor_id, valid_from, known_at)
        if old and old != person_id and action == "bind":
            raise ContractError("collision needs explicit audited merge or split")
        self.s.db.execute("INSERT INTO aliases(provider,vendor_id,person_id,valid_from,valid_to,known_at) VALUES(?,?,?,?,?,?)",
            (provider, vendor_id, person_id, start, end, known))
        self.s.db.execute("INSERT INTO identity_audit(action,body,known_at) VALUES(?,?,?)",
            (action, canonical(dict(provider=provider, vendor_id=vendor_id, old=old,
             person_id=person_id, reason=reason, valid_from=start, valid_to=end)), known))

    def register(self, raw: dict) -> None:
        for key in ("id", "person_id", "team_id", "source_id"):
            identifier(raw[key], key)
        start, known = instant(raw["valid_from"]), instant(raw["known_at"])
        end = instant(raw["valid_to"]) if raw.get("valid_to") else None
        if end and end <= start:
            raise ContractError("empty roster interval")
        if raw["kind"] not in {"active", "loan", "youth", "reserve", "unknown"}:
            raise ContractError("unsupported registration kind")
        confidence = finite(raw.get("confidence", 1), 0, 1, "confidence")
        self.s.source(raw["source_id"])
        self.s.db.execute("INSERT INTO registrations VALUES(?,?,?,?,?,?,?,?,?)",
            (raw["id"], raw["person_id"], raw["team_id"], start, end, known,
             raw["kind"], raw["source_id"], confidence))

    def roster(self, team: str, valid_at: str, known_at: str) -> list[dict]:
        rows = self.s.db.execute("SELECT r.*,p.name FROM registrations r JOIN persons p ON p.id=r.person_id WHERE r.team_id=? AND r.valid_from<=? AND (r.valid_to IS NULL OR r.valid_to>?) AND r.known_at<=? ORDER BY r.known_at DESC", (team, instant(valid_at), instant(valid_at), instant(known_at)))
        result = {}
        for row in rows:
            result.setdefault(row["person_id"], dict(row))
        return list(result.values())

    def history(self) -> list[dict]:
        return [{**dict(r), "body": json.loads(r["body"])} for r in self.s.db.execute("SELECT * FROM identity_audit ORDER BY seq")]
