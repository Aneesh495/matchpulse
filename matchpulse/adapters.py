"""Normalize operator-supplied authorized archive files without redistributing them."""
from __future__ import annotations
from datetime import datetime,timedelta
import json
from pathlib import Path
from .contracts import ContractError,Envelope,identifier,instant

POSITION={1:'GK',2:'FB',3:'CB',4:'CB',5:'CB',6:'FB',7:'FB',8:'FB',9:'DM',10:'DM',11:'DM',12:'CM',13:'CM',14:'CM',15:'WG',16:'WG',17:'AM',18:'AM',19:'AM',20:'WG',21:'WG',22:'ST',23:'ST',24:'ST',25:'ST'}
TYPE_MAP={'Pass':'pass','Carry':'carry','Shot':'shot','Ball Recovery':'recovery','Dispossessed':'loss','Duel':'duel','Pressure':'pressure','Clearance':'clearance','Foul Committed':'foul','Offside':'offside','Half End':'phase'}


def bounded_json(path:Path,max_bytes:int=30_000_000):
    if path.stat().st_size>max_bytes:raise ContractError('archive file exceeds bound')
    value=json.loads(path.read_text())
    if not isinstance(value,list) or len(value)>50000:raise ContractError('bounded event list required')
    return value


def statsbomb_archive(events:list[dict],lineups:list[dict],metadata:dict,rights:dict,acquired_at:str)->dict:
    if not rights.get('local_research_authorized') or rights.get('mode')!='archive':
        raise ContractError('operator must configure authorized local archive use')
    if not rights.get('terms_url','').startswith('https://'):raise ContractError('source terms URL required')
    license_id=identifier(rights['id'])
    mid='statsbomb-'+identifier(str(metadata['match_id']))
    kickoff=datetime.fromisoformat(instant(metadata['kickoff']))
    acquired=datetime.fromisoformat(instant(acquired_at))
    home_id='sb-team-'+str(metadata['home_team']['home_team_id'])
    away_id='sb-team-'+str(metadata['away_team']['away_team_id'])
    people={};initial={}
    for e in events:
        if e.get('type',{}).get('name')=='Starting XI':
            tid='sb-team-'+str(e['team']['id'])
            for p in e['tactics']['lineup']:
                pid='sb-person-'+str(p['player']['id'])
                initial[pid]=(POSITION.get(p['position']['id'],'CM'),tid)
    for lineup in lineups:
        tid='sb-team-'+str(lineup['team_id'])
        for p in lineup['lineup']:
            pid='sb-person-'+str(p['player_id'])
            people[pid]=dict(id=pid,name=p['player_name'],team_id=tid,role=initial.get(pid,('CM',tid))[0],birth_date=None,country=None)
    if not people or not initial:raise ContractError('complete starting XI and roster required')
    normalized=[]
    def add(raw:dict,kind:str,player:str|None,team:str|None,payload:dict,second:float,period:int,ordinal:int):
        occurred=kickoff+timedelta(seconds={1:0,2:2700,3:5400,4:6300,5:7200}.get(period,0)+second)
        if occurred>acquired:raise ContractError('archive acquired before fixture occurred')
        e=Envelope.parse(dict(match_id=mid,event_id=str(raw['id']),revision=1,ordinal=ordinal,
            occurred_at=occurred.isoformat(),published_at=None,received_at=(acquired+timedelta(microseconds=len(normalized))).isoformat(),
            provider='statsbomb',license_id=license_id,mode='archive',kind=kind,player_id=player,team_id=team,period=period,second=second,payload=payload))
        normalized.append(e.wire())
    for i,(pid,(role,tid)) in enumerate(sorted(initial.items())):
        add(dict(id='lineup-'+pid),'lineup',pid,tid,dict(role=role,starter=True),0,1,i+1)
    offset=len(normalized)
    skipped={}
    for i,raw in enumerate(events):
        kind_name=raw.get('type',{}).get('name')
        if kind_name in {'Starting XI','Half Start'}:continue
        period=int(raw['period'])
        hh,mm,ss=raw.get('timestamp','00:00:00').split(':');second=int(hh)*3600+int(mm)*60+float(ss)
        pid='sb-person-'+str(raw['player']['id']) if raw.get('player') else None
        tid='sb-team-'+str(raw['team']['id']) if raw.get('team') else None
        payload={};kind=TYPE_MAP.get(kind_name)
        location=raw.get('location')
        if location and len(location)>=2:payload.update(x=location[0],y=location[1])
        if kind_name=='Pass':
            p=raw['pass'];end=p.get('end_location')
            if end:payload.update(end_x=end[0],end_y=end[1])
            payload['success']='outcome' not in p
        elif kind_name=='Carry':
            end=raw['carry'].get('end_location')
            if end:payload.update(end_x=end[0],end_y=end[1])
        elif kind_name=='Shot':
            p=raw['shot'];payload.update(outcome='goal' if p.get('outcome',{}).get('name')=='Goal' else 'not-goal')
            if 'statsbomb_xg' in p:payload.update(xg=p['statsbomb_xg'],xg_definition='StatsBomb provider shot model, exact version unknown')
        elif kind_name=='Substitution':
            on='sb-person-'+str(raw['substitution']['replacement']['id'])
            if on not in people:raise ContractError('substitute not in acquired roster')
            kind='substitution';payload.update(off=pid,on=on)
        elif kind_name=='Own Goal Against':kind='own_goal'
        elif kind_name=='Bad Behaviour' or kind_name=='Foul Committed':
            card=raw.get('bad_behaviour',raw.get('foul_committed',{})).get('card',{}).get('name')
            if card in {'Red Card','Second Yellow'}:kind='red'
            elif card=='Yellow Card':kind='yellow'
        elif kind_name=='Duel':payload['success']=raw.get('duel',{}).get('outcome',{}).get('name') in {'Won','Success','Success In Play','Success Out'}
        elif kind_name=='Half End':
            payload['phase']='period-end'
            # Match metadata must explicitly mark completion; interrupted archives cannot look final.
            if metadata.get('complete') and period==metadata.get('final_period',2):kind='end'
        if kind is None:
            skipped[kind_name]=skipped.get(kind_name,0)+1;continue
        if pid and pid not in people:raise ContractError('unresolved vendor person identifier')
        add(raw,kind,pid,tid,payload,second,period,offset+i+1)
    fixture=dict(id=mid,home_id=home_id,away_id=away_id,home=metadata['home_team']['home_team_name'],away=metadata['away_team']['away_team_name'],competition=metadata.get('competition','StatsBomb archive'),date=kickoff.date().isoformat(),mode='archive',trusted=False,players=list(people.values()))
    source=dict(id=license_id,name=rights.get('name','StatsBomb local research archive'),mode='archive',terms_url=rights['terms_url'],redistribution=bool(rights.get('redistribution',False)),acquired_at=acquired_at)
    return dict(packet=dict(sources=[source],fixtures=[fixture]),events=normalized,skipped=skipped,
        support=dict(provider_publication='unknown',historical_live_clock='unavailable',xg='provider defined, version unknown',off_ball='unsupported',physical_load='unsupported'),
        warning='Archive snapshot lacks historical provider revision and publication times. Do not represent it as live history.')
