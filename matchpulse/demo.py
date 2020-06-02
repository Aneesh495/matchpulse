"""Authored fictional fixture for correction and ticker mechanics, not research evidence."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from .contracts import ContractError, canonical
from .engine import Engine

MATCH_ID = "demo-harbor-athletic"
BASE = datetime(2024, 6, 8, 18, tzinfo=timezone.utc)


def packet() -> dict:
    names = [("Luca Ferri","GK"),("Noah Ellis","CB"),("Arun Shah","CB"),("Milo Costa","FB"),
        ("Elias Berg","DM"),("Theo Laurent","CM"),("Adam Vale","AM"),("Nico Reed","WG"),
        ("Leo Marin","ST"),("Oscar Hart","FB"),("Max Silva","WG"),("Finn Walsh","CM"),
        ("Jonas Weber","GK"),("Rafael Cruz","CB"),("Ben Cole","CB"),("Alex Rossi","FB"),
        ("Ivan Novak","DM"),("Sam Hill","CM"),("Louis Moreau","AM"),("Kai Adler","WG"),
        ("Tom de Vries","ST"),("Hugo Blanc","FB"),("Amir Haddad","WG"),("Emil Strand","ST")]
    players=[]
    for i,(name,role) in enumerate(names):
        players.append(dict(id=f"demo-p{i+1}",name=name,role=role,team_id="harbor" if i<12 else "athletic",
            birth_date=f"{1997+i%7}-03-12",country=None,synthetic_prior_eur=round((3+(i*7)%34)*1e6)))
    context=[]
    for p in players:
        context.append(dict(id="registration-"+p["id"],revision=1,person_id=p["id"],kind="registration",
            valid_from=BASE.isoformat(),valid_to=None,known_at=BASE.isoformat(),source_id="authored-cc0",
            source_url="https://example.org/fictional-roster",confidence=1.0,
            details=dict(team_id=p["team_id"],registration_kind="active")))
    context.append(dict(id="contract-demo-p9",revision=1,person_id="demo-p9",kind="contract",
        valid_from=BASE.isoformat(),valid_to="2027-06-30T00:00:00Z",known_at=BASE.isoformat(),source_id="authored-cc0",
        source_url="https://example.org/fictional-contract",confidence=1.0,
        details=dict(team_id="harbor",expires_at="2027-06-30T00:00:00Z")))
    return dict(context=context,sources=[dict(id="authored-cc0",mode="synthetic",name="Authored Matchpulse diagnostic fixture",terms_url="https://creativecommons.org/publicdomain/zero/1.0/",redistribution=True,freshness_seconds=None,acquired_at=BASE.isoformat())],
        fixtures=[dict(id=MATCH_ID,home_id="harbor",away_id="athletic",home="Harbor FC",away="Athletic Union",competition="Research exhibition",date="2024-06-08",mode="synthetic",trusted=False,players=players)])


def deliveries() -> list[dict]:
    results=[]
    def add(eid,kind,second=0,period=1,player=None,team=None,payload=None,revision=1):
        i=len(results)+1
        occurred=BASE+timedelta(seconds=(period-1)*2700+second)
        received=BASE+timedelta(seconds=7200+i*3)
        results.append(dict(match_id=MATCH_ID,event_id=eid,revision=revision,ordinal=i,
            occurred_at=occurred.isoformat(),published_at=None,received_at=received.isoformat(),
            provider="authored",license_id="authored-cc0",mode="synthetic",kind=kind,
            player_id=player,team_id=team,period=period,second=second,payload=payload or {}))
    for i,p in enumerate(packet()["fixtures"][0]["players"]):
        add(f"lineup-{i}","lineup",player=p["id"],team=p["team_id"],payload=dict(role=p["role"],starter=i not in {11,23}))
    add("pass-1","pass",120,player="demo-p6",team="harbor",payload=dict(x=44,y=34,end_x=81,end_y=30,success=True))
    add("carry-1","carry",480,player="demo-p8",team="harbor",payload=dict(x=66,y=65,end_x=103,end_y=50,success=True))
    add("save-1","save",900,player="demo-p1",team="harbor",payload=dict(xg=0.42,xg_definition="authored-known-truth-test-v1"))
    add("goal-var","goal",1800,player="demo-p9",team="harbor",payload=dict(x=108,y=40,xg=0.6,xg_definition="authored-known-truth-test-v1"))
    add("red-1","red",2000,player="demo-p17",team="athletic")
    add("var-1","retract",2020,payload=dict(target="goal-var",reason="VAR: attacker offside, goal overturned"))
    add("role-1","role",2100,player="demo-p7",team="harbor",payload=dict(role="CM",reason="revised tactical role"))
    # Deliberately delivered late after VAR, but sorted before the original goal.
    add("late-pass","pass",1500,player="demo-p19",team="athletic",payload=dict(x=45,y=30,end_x=72,end_y=45,success=True))
    add("half","phase",2700,payload=dict(phase="half-time"))
    add("sub-1","substitution",600,period=2,team="harbor",payload=dict(off="demo-p6",on="demo-p12",role="CM"))
    add("goal-final","goal",1200,period=2,player="demo-p9",team="harbor",payload=dict(x=112,y=40,xg=0.35,xg_definition="authored-known-truth-test-v1"))
    add("goal-final","goal",1200,period=2,player="demo-p9",team="harbor",revision=2,payload=dict(x=112,y=40,xg=0.28,xg_definition="authored-known-truth-test-v1",reason="shot-quality correction"))
    add("end","end",2820,period=2,payload=dict(phase="full-time"))
    return results


def later_deal() -> dict:
    return dict(id="demo-later-sale",person_id="demo-p9",kind="permanent",disclosure="exact",
        effective_at="2024-07-01T00:00:00Z",known_at="2024-07-01T12:00:00Z",currency="EUR",
        guaranteed=19e6,lower=None,upper=None,addons_upper=2e6,
        source_url="https://example.org/fictional-club-release",source_id="authored-cc0",mode="synthetic")


def step(engine: Engine, finish: bool = False) -> dict:
    key="replay-index:"+MATCH_ID
    row=engine.s.db.execute("SELECT value FROM metadata WHERE key=?",(key,)).fetchone()
    index=int(row[0]) if row else 0
    events=deliveries()
    if index<len(events):
        for e in events[index:] if finish else events[index:index+1]:
            engine.ingest(e)
            index+=1
            engine.s.db.execute("INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,str(index)))
        return dict(index=index,total=len(events)+1,done=False,kind="event",snapshot=engine.snapshot())
    if index==len(events):
        engine.deal(later_deal())
        index+=1
        engine.s.db.execute("INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,str(index)))
    return dict(index=index,total=len(events)+1,done=True,kind="transaction",snapshot=engine.snapshot())
