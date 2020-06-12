"""Source-bound engineering diagnostics. Full campaigns refuse missing real inputs."""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time
from .contracts import ContractError,canonical,digest
from .storage import Store
from .engine import Engine
from .demo import packet,deliveries,later_deal,MATCH_ID
from .numerics import atomic_json
from .resources import guard,doctor


def source_inputs(root:Path)->dict:
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    files=subprocess.check_output(['git','ls-files'],cwd=root,text=True).splitlines()
    return dict(commit=commit,files={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files if (root/p).is_file()})


def seal(directory:Path)->None:
    manifest={str(p.relative_to(directory)):hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.rglob('*') if p.is_file() and p.name!='MANIFEST.json'}
    atomic_json(directory/'MANIFEST.json',dict(format='matchpulse-evidence-v1',files=manifest))


def campaign(root:Path,out:Path,profile:str='diagnostic')->dict:
    resources=guard(root,50_000_000)
    out.mkdir(parents=True,exist_ok=False)
    source=source_inputs(root)
    atomic_json(out/'SOURCE_INPUTS.json',source)
    atomic_json(out/'ENVIRONMENT.json',doctor(root))
    atomic_json(out/'RESOURCES.json',resources)
    atomic_json(out/'DATASETS.json',dict(mode='synthetic',generator='authored-generator-v1',actual_matches=0,actual_transactions=0,fixture_hash=digest(packet()),deliveries_hash=digest(deliveries()),source_license='CC0 authored fixture'))
    (out/'COMMANDS.jsonl').write_text(canonical(dict(argv=sys.argv,profile=profile,started_ns=time.time_ns()))+'\n')
    if profile=='full':
        result=dict(profile='full',status='blocked',failed=[],blocked=['G01 lawful large data and coverage','G07 learned actual-data rating campaign','G10 actual transaction rolling calibration','G13 licensed live fixture','Europe-wide roster reconciliation','independent expert review'],actual_matches=0,actual_transactions=0)
        atomic_json(out/'ACCEPTANCE.json',result)
        with (out/'COMMANDS.jsonl').open('a') as log:log.write(canonical(dict(completed_ns=time.time_ns(),exit_code=2,status='blocked'))+'\n')
        seal(out)
        return result
    if profile!='diagnostic':raise ContractError('unknown campaign profile')
    events=deliveries();atomic_json(out/'PACKET.json',packet())
    (out/'DELIVERIES.jsonl').write_text(''.join(canonical(e)+'\n' for e in events))
    s=Store(out/'replay.db');engine=Engine(s);engine.seed(packet())
    snapshots=[];observations=[]
    for event in events:
        result=engine.ingest(event);snapshots.append(result['snapshot'])
        observations.append(dict(event_id=event['event_id'],revision=event['revision'],processing_ms=result['processing_ms'],version=result['version'],mode='synthetic',upstream_age_seconds=None,timing=result['timing']))
    engine.deal(later_deal())
    undisclosed={**later_deal(),'id':'demo-undisclosed','person_id':'demo-p8','disclosure':'undisclosed','guaranteed':None,'addons_upper':None}
    engine.deal(undisclosed)
    atomic_json(out/'TRANSACTIONS.json',dict(records=[later_deal(),undisclosed]))
    before=engine.snapshot();duplicate=engine.ingest(events[-1]);assert duplicate['duplicate']
    s.close();s=Store(out/'replay.db');engine=Engine(s)
    restart_equal=before==engine.snapshot();s.close()
    (out/'SNAPSHOTS.jsonl').write_text(''.join(canonical(v)+'\n' for v in snapshots))
    (out/'OBSERVATIONS.jsonl').write_text(''.join(canonical(v)+'\n' for v in observations))
    atomic_json(out/'FINAL.json',before)
    # A late fixture is interleaved rather than cloning event counts as actual data.
    stress=Store(':memory:');interleaved=Engine(stress);times=[];fixture_ids=[]
    for i in range(16):
        p=copy.deepcopy(packet());p['fixtures'][0]['id']=f'load-{i}'
        interleaved.seed(p);fixture_ids.append(f'load-{i}')
    stress_rows=[];resource_samples=[]
    for event in events:
        usage=resource.getrusage(resource.RUSAGE_SELF)
        resource_samples.append(dict(event_id=event['event_id'],monotonic_ns=time.monotonic_ns(),max_rss_bytes=usage.ru_maxrss*(1 if sys.platform=='darwin' else 1024),user_cpu_seconds=usage.ru_utime,system_cpu_seconds=usage.ru_stime))
        for mid in fixture_ids:
            adapted={**event,'match_id':mid}
            result=interleaved.ingest(adapted);times.append(result['processing_ms'])
            stress_rows.append(dict(match_id=mid,event_id=event['event_id'],revision=event['revision'],processing_ms=result['processing_ms'],retraction=event['kind']=='retract',version=result['version'],timing=result['timing']))
    stress.close()
    (out/'LOAD.jsonl').write_text(''.join(canonical(v)+'\n' for v in stress_rows))
    ordered=sorted(times);p95=ordered[math_ceil(.95*len(ordered))-1]
    result=dict(profile='diagnostic',status='passed' if restart_equal and p95<=250 else 'failed',full_acceptance='blocked',
        units=dict(synthetic_matches=16,normalized_deliveries=len(times),actual_matches=0,transactions=2,actual_transactions=0),
        p95_processing_ms=p95,processing_budget_ms=250,upstream_freshness='unmeasured; no licensed live source',restart_equal=restart_equal,
        source_commit=source['commit'],required_event_count=37,final_score=before['matches'][0]['score'],ticker_estimates=len(before['ticker']),
        limitations=['serialized bounded recomputation, not optimized incremental state','no genuine live fixture','no large actual-data campaign','no empirical rating calibration'])
    atomic_json(out/'ACCEPTANCE.json',result)
    (out/'RESOURCE_SAMPLES.jsonl').write_text(''.join(canonical(v)+'\n' for v in resource_samples))
    with (out/'COMMANDS.jsonl').open('a') as log:log.write(canonical(dict(completed_ns=time.time_ns(),exit_code=0 if result['status']=='passed' else 2,status=result['status']))+'\n')
    atomic_json(out/'REQUIREMENTS.json',dict(G03='diagnostic replay exercised',G04='diagnostic rollback and restart exercised',G06='baseline only',G12='diagnostic ticker exercised',G13='blocked',G14='diagnostic backend load; browser concurrent resume verified separately'))
    seal(out)
    return result


def math_ceil(value:float)->int:
    return int(value) if value==int(value) else int(value)+1
