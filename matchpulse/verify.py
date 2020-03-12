"""Independent bundle audit. Saved status booleans are not acceptance evidence."""
from __future__ import annotations
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys


class VerificationError(ValueError):pass


def require(condition:bool,message:str)->None:
    if not condition:raise VerificationError(message)


def json_file(path:Path):
    try:return json.loads(path.read_text(),parse_constant=lambda x:(_ for _ in ()).throw(VerificationError('nonfinite JSON')))
    except (OSError,json.JSONDecodeError) as exc:raise VerificationError(str(exc)) from exc


def rows(path:Path)->list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def verify(directory:Path,source:Path,expected_commit:str)->dict:
    require(directory.is_dir(),'missing evidence directory')
    files=list(directory.rglob('*'))
    require(len(files)<=100 and sum(p.stat().st_size for p in files if p.is_file())<=100_000_000,'evidence resource bound exceeded')
    manifest=json_file(directory/'MANIFEST.json')['files']
    required={'SOURCE_INPUTS.json','DATASETS.json','ENVIRONMENT.json','COMMANDS.jsonl','ACCEPTANCE.json','PACKET.json','DELIVERIES.jsonl','SNAPSHOTS.jsonl','OBSERVATIONS.jsonl','LOAD.jsonl','FINAL.json','TRANSACTIONS.json','REQUIREMENTS.json'}
    require(required.issubset(manifest),'missing required execution artifact')
    actual={str(p.relative_to(directory)) for p in files if p.is_file() and p.name!='MANIFEST.json'}
    require(set(manifest)==actual,'manifest file set mismatch')
    for name,sha in manifest.items():
        p=directory/name
        require(not p.is_symlink() and p.resolve().is_relative_to(directory.resolve()),'unsafe artifact path')
        require(hashlib.sha256(p.read_bytes()).hexdigest()==sha,'artifact checksum mismatch: '+name)
    claimed=json_file(directory/'SOURCE_INPUTS.json')
    require(claimed['commit']==expected_commit,'source mismatch against trusted expected commit')
    current=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    require(current==expected_commit,'replay checkout is not expected commit')
    trusted_paths=subprocess.check_output(['git','ls-tree','-r','--name-only',expected_commit],cwd=source,text=True).splitlines()
    require(set(claimed['files'])==set(trusted_paths),'source manifest omits tracked files')
    for name,sha in claimed['files'].items():
        raw=subprocess.check_output(['git','show',f'{expected_commit}:{name}'],cwd=source)
        require(hashlib.sha256(raw).hexdigest()==sha,'source hash does not match trusted Git objects')
        require(hashlib.sha256((source/name).read_bytes()).hexdigest()==sha,'source checkout changed after freeze')
    probes=json_file(source/'fixtures/probes.json')
    data=json_file(directory/'DATASETS.json')
    require(data['mode']=='synthetic' and data['actual_matches']==0 and data['actual_transactions']==0,'forged actual-data coverage')
    events=rows(directory/'DELIVERIES.jsonl');snapshots=rows(directory/'SNAPSHOTS.jsonl')
    require(len(events)==probes['expected_deliveries']==len(snapshots),'incomplete replay workload')
    latest={};retracted=set();seen_goals=[]
    for i,(event,snapshot) in enumerate(zip(events,snapshots)):
        key=(event['provider'],event['event_id'])
        if key not in latest or latest[key]['revision']<event['revision']:latest[key]=event
        retracted={e['payload']['target'] for e in latest.values() if e['kind']=='retract'}
        score=[0,0]
        for e in latest.values():
            if e['event_id'] in retracted or e['period']==5:continue
            if e['kind']=='goal' or e['kind']=='shot' and e['payload'].get('outcome')=='goal':
                score[0 if e['team_id']=='harbor' else 1]+=1
        require(snapshot['version']==i+1,'snapshot sequence gap')
        require(snapshot['score']==score,'independent goal/retraction replay mismatch')
        require(snapshot['model_id']==probes['expected_rating_model'],'wrong rating model identity')
        seen_goals.append(score)
        event_clock=(event['period'],event['second'],event['ordinal'],event['event_id'])
        for value in snapshot['action_values']:
            require(value['known_at']<=snapshot['known_at'],'future correction leaked into prior snapshot')
            require(math.isfinite(value['value']),'nonfinite contribution')
            referenced=[e for e in latest.values() if e['event_id']==value['event_id'] and e['revision']==value['revision']]
            require(len(referenced)==1,'action references future or unknown event revision')
            e=referenced[0]
            require(datetime.fromisoformat(e['received_at'])==datetime.fromisoformat(value['known_at']),'feature known-at provenance mismatch')
            if e['kind']=='pass':
                # The declared reference only sees actual score and man advantage before this action.
                order=sorted([x for x in latest.values() if x['kind']!='retract' and x['event_id'] not in retracted],key=lambda x:(x['period'],x['second'],x['ordinal'],x['event_id']))
                diff=0;advantage=0
                for x in order:
                    if x['event_id']==e['event_id']:break
                    if x['kind']=='goal':diff+=1 if x['team_id']==e['team_id'] else -1
                    if x['kind']=='red':advantage+=-1 if x['team_id']==e['team_id'] else 1
                x,y=e['payload']['x'],e['payload']['y']
                logit=-1.9-math.hypot(120-x,(40-y)*.6)/22-diff*.04+advantage*.12
                p=1/(1+math.exp(-logit))
                require(abs(value['before'][0]-p)<1e-10,'event-then-future feature leakage')
    require([1,0] in seen_goals and [0,0] in seen_goals,'missing provisional or overturned state')
    final=json_file(directory/'FINAL.json');m=final['matches'][0]
    require(m['score']==probes['expected_score'],'wrong final score')
    ps={p['id']:p for p in m['players']}
    require(ps[probes['unused_player']]['rating'] is None,'unused substitute received a rating')
    require(abs(ps[probes['save_player']]['contribution']-probes['save_contribution'])<1e-8,'goalkeeper attribution mismatch')
    require(abs(ps[probes['dismissed_player']]['minutes']-probes['dismissal_minutes'])<1e-3,'dismissal exposure mismatch')
    require(len(final['ticker'])==probes['expected_estimates'],'missing eligible estimates')
    for estimate in final['ticker']:
        require(estimate['model_id']==probes['expected_value_model'],'wrong valuation model ID')
        require(estimate['mode']=='synthetic' and estimate['target'].startswith('guaranteed consideration conditional'),'invalid valuation estimand')
        require(estimate['known_at']==m['known_at'],'estimate known-at mismatch')
    transactions=json_file(directory/'TRANSACTIONS.json')['records']
    for d in transactions:
        if d['disclosure']=='undisclosed':require(d['guaranteed'] is None and d['lower'] is None and d['upper'] is None,'fee replaced an undisclosed amount')
        if d['kind']=='none':require(d['guaranteed'] is None,'no move became a fee')
    observations=rows(directory/'OBSERVATIONS.jsonl')
    require(len(observations)==len(events),'missing processing observations')
    for row in observations:
        require(row['mode']=='synthetic' and row['upstream_age_seconds'] is None,'forged feed freshness')
    load=rows(directory/'LOAD.jsonl')
    require(len(load)==16*37,'incomplete concurrent fixture workload')
    require(len({r['match_id'] for r in load})==16,'load fixture denominator mismatch')
    for r in load:require(math.isfinite(r['processing_ms']) and r['processing_ms']>0,'invalid processing timing')
    require(sum(r['retraction'] for r in load)==16,'retractions omitted from processing measurements')
    p95=sorted(r['processing_ms'] for r in load)[math.ceil(.95*len(load))-1]
    require(p95<=250,'processing SLO failed')
    reported=json_file(directory/'ACCEPTANCE.json')
    require(reported['profile']=='diagnostic' and reported['full_acceptance']=='blocked','diagnostic masquerades as full acceptance')
    require(abs(p95-reported['p95_processing_ms'])<1e-8,'summary p95 differs from raw observations')
    replay=subprocess.run([sys.executable,'-m','matchpulse.audit_replay',str(directory.resolve())],cwd=source,text=True,capture_output=True,timeout=20)
    require(replay.returncode==0,'saved-engine replay failed: '+replay.stderr[-300:])
    rebuilt=json.loads(replay.stdout)
    require(rebuilt==final,'saved-engine bounded replay differs from evidence')
    return dict(status='passed',profile='diagnostic',full_acceptance='blocked',source_commit=expected_commit,events=len(events),p95_processing_ms=p95,semantic_checks=['freshness','disclosure','future-feature','model-id','score-retractions','exposure','saved-engine-replay'])


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);p.add_argument('--source',type=Path,default=Path.cwd());p.add_argument('--expected-commit',required=True)
    a=p.parse_args()
    try:print(json.dumps(verify(a.evidence,a.source,a.expected_commit),sort_keys=True))
    except (VerificationError,KeyError,OSError,ValueError,subprocess.SubprocessError) as exc:
        print(json.dumps(dict(status='failed',reason=str(exc))),file=sys.stderr);sys.exit(1)


if __name__=='__main__':main()
