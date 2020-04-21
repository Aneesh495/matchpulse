"""Concurrent loopback HTTP fixtures with durable stream reconnection observations."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import tempfile
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from matchpulse.demo import packet,deliveries
from matchpulse.engine import Engine
from matchpulse.storage import Store
from matchpulse.resources import guard
from matchpulse.numerics import atomic_json
from matchpulse.contracts import canonical,identifier

run=identifier(sys.argv[1]);out=root/'evidence'/run;guard(root,50_000_000);out.mkdir(parents=True,exist_ok=False)
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
s=Store(out/'load.db');e=Engine(s)
for i in range(16):
    p=copy.deepcopy(packet());p['fixtures'][0]['id']=f'http-load-{i}';e.seed(p)
s.close()
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
base=f'http://127.0.0.1:{port}'
log=(out/'server.log').open('w')
process=subprocess.Popen([str(root/'bin/matchpulse'),'-addr',f'127.0.0.1:{port}','-db',str(out/'load.db'),'-assets',str(root/'dist')],cwd=root,stdout=log,stderr=log)
observations=[];streams=[]
def request(event):
    start=time.perf_counter()
    req=urllib.request.Request(base+'/api/ingest',data=canonical(event).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=10) as response:result=json.load(response)
    return dict(match_id=event['match_id'],event_id=event['event_id'],revision=event['revision'],kind=event['kind'],roundtrip_ms=(time.perf_counter()-start)*1000,processing_ms=result['processing_ms'],version=result['version'],stream_seq=result['stream_seq'])
def stream(after):
    req=urllib.request.Request(base+'/api/events',headers={'Last-Event-ID':str(after)})
    with urllib.request.urlopen(req,timeout=5) as response:
        ids=[]
        while len(ids)<8:
            line=response.readline().decode()
            if line.startswith('id: '):ids.append(int(line[4:]))
            if line.startswith('event: recovery'):
                while response.readline()!=b'\n':pass
                break
        return dict(after=after,ids=ids)
try:
    for attempt in range(60):
        if process.poll() is not None:raise RuntimeError('load server exited')
        try:
            urllib.request.urlopen(base+'/api/health',timeout=.2).close();break
        except OSError:time.sleep(.1)
    else:raise RuntimeError('load server did not become ready')
    with ThreadPoolExecutor(max_workers=16) as pool:
        for raw in deliveries():
            events=[{**raw,'match_id':f'http-load-{i}'} for i in range(16)]
            observations.extend(pool.map(request,events))
        # Each reconnect reads a distinct durable prefix chosen before inspection.
        streams=list(pool.map(stream,[1,10,20,30,40,50,60,70]))
    for trace in streams:
        if trace['ids']!=sorted(set(trace['ids'])) or min(trace['ids'])<=trace['after']:raise RuntimeError('stream resume sequence failure')
    with urllib.request.urlopen(base+'/api/state',timeout=10) as response:state=json.load(response)
    measured=[m for m in state['matches'] if m['id'].startswith('http-load-')]
    if len(measured)!=16 or any(m['score']!=[1,0] or m['version']!=37 for m in measured):raise RuntimeError('concurrent fixture final state mismatch')
    ordered=sorted(r['roundtrip_ms'] for r in observations);p95=ordered[(95*len(ordered)+99)//100-1]
    (out/'HTTP.jsonl').write_text(''.join(canonical(r)+'\n' for r in observations))
    atomic_json(out/'STREAMS.json',dict(records=streams))
    atomic_json(out/'FINAL.json',state)
    result=dict(profile='synthetic-loopback-http',source_commit=source,concurrent_callers=16,deliveries=len(observations),reconnecting_clients=len(streams),p95_roundtrip_ms=p95,processing_budget_ms=250,status='passed' if p95<=250 else 'failed',upstream_freshness='not measured; synthetic replay',actual_fixtures=0)
    atomic_json(out/'REPORT.json',result);print(canonical(result))
    if result['status']!='passed':raise SystemExit(1)
finally:
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:process.kill();process.wait()
    log.close()
