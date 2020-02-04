"""Domain transaction boundary: journal, derived versions, and outbox commit together."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import time
from .contracts import ContractError, Envelope, canonical, identifier, instant
from .identity import Identity
from .ratings import RatingReducer
from .storage import Store
from .valuation import Deal, diagnostic_estimate


class Engine:
    def __init__(self, store: Store):
        self.s = store
        self.identity = Identity(store)

    def seed(self, packet: dict) -> dict:
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
        return {"fixtures": len(packet.get("fixtures", []))}

    def ingest(self, raw: dict, failpoint: str | None = None) -> dict:
        start=time.perf_counter()
        event=Envelope.parse(raw)
        with self.s.transaction():
            seq, inserted=self.s.append(event)
            if not inserted:
                return {"duplicate":True,"journal_seq":seq,"snapshot":self.s.latest(event.match_id)}
            if failpoint == "after-journal":
                raise RuntimeError("injected failure after journal append")
            fixture=self.s.fixture(event.match_id)
            events=self.s.events(event.match_id)
            if len(events)>50000:
                raise ContractError("match journal capacity exceeded")
            current=RatingReducer(fixture).run(events)
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
            if failpoint=="before-commit":
                raise RuntimeError("injected failure before commit")
        return dict(duplicate=False,journal_seq=seq,stream_seq=stream_seq,version=version,
            corrected=bool(corrected),processing_ms=(time.perf_counter()-start)*1000,snapshot=current)

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

    def ticker(self, cutoff: str | None = None) -> list[dict]:
        query="SELECT * FROM estimates"
        args=[]
        if cutoff:
            query+=" WHERE known_at<=?";args.append(instant(cutoff))
        results={}
        for r in self.s.db.execute(query+" ORDER BY seq DESC",args):
            results.setdefault(r["person_id"],json.loads(r["body"]))
        for p,result in results.items():
            deals=self.s.db.execute("SELECT body FROM deals WHERE person_id=?"+(" AND known_at<=?" if cutoff else "")+" ORDER BY known_at",(p,instant(cutoff)) if cutoff else (p,))
            result["transactions"]=[json.loads(d[0]) for d in deals]
        return list(results.values())

    def history(self, person_id: str) -> dict:
        return dict(estimates=[json.loads(r[0]) for r in self.s.db.execute("SELECT body FROM estimates WHERE person_id=? ORDER BY seq",(person_id,))],
            transactions=[json.loads(r[0]) for r in self.s.db.execute("SELECT body FROM deals WHERE person_id=? ORDER BY known_at",(person_id,))])

    def deal(self, raw: dict) -> dict:
        d=Deal.parse(raw)
        self.s.source(d.source_id)
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
