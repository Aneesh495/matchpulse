"""Semantic evidence tampering with ordinary hashes recomputed before verification."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from .campaign import seal
from .contracts import canonical
from .numerics import atomic_json


def controls(bundle:Path,source:Path,commit:str,out:Path)->dict:
    from .verify import verify
    verify(bundle,source,commit)
    reports=[]
    out.mkdir(parents=True,exist_ok=False)
    def rewrite(path:Path,value):path.write_text(canonical(value)+'\n')
    def edit(case:Path,name:str):
        if name=='forged-feed-freshness':
            path=case/'OBSERVATIONS.jsonl';rows=[json.loads(x) for x in path.read_text().splitlines()];rows[0].update(mode='live',upstream_age_seconds=.01);path.write_text(''.join(canonical(r)+'\n' for r in rows))
        elif name=='undisclosed-as-fee':
            p=case/'TRANSACTIONS.json';v=json.loads(p.read_text());v['records'][1]['guaranteed']=35e6;rewrite(p,v)
        elif name=='future-event-feature':
            p=case/'SNAPSHOTS.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()]
            for row in rows:
                if row['action_values']:
                    row['action_values'][0]['before'][0]+=.1;break
            p.write_text(''.join(canonical(r)+'\n' for r in rows))
        elif name=='wrong-value-model':
            p=case/'FINAL.json';v=json.loads(p.read_text());v['ticker'][0]['model_id']='forged-model-v999';rewrite(p,v)
        elif name=='missing-artifact':(case/'LOAD.jsonl').unlink()
        elif name=='failed-replay':
            p=case/'FINAL.json';v=json.loads(p.read_text());v['seq']+=100;rewrite(p,v)
        elif name=='corruption':(case/'FINAL.json').write_bytes(b'{corrupt')
    cases=['forged-feed-freshness','undisclosed-as-fee','future-event-feature','wrong-value-model','missing-artifact','failed-replay','corruption','source-mismatch']
    for name in cases:
        with tempfile.TemporaryDirectory(prefix='control-',dir=source/'.agent-local') as temp:
            case=Path(temp)/'bundle';shutil.copytree(bundle,case)
            edit(case,name)
            if name!='corruption':
                (case/'MANIFEST.json').unlink();seal(case)
            expected='0'*40 if name=='source-mismatch' else commit
            cmd=[sys.executable,'-m','matchpulse.verify',str(case),'--source',str(source),'--expected-commit',expected]
            p=subprocess.run(cmd,cwd=source,text=True,capture_output=True,timeout=30)
            report=dict(case=name,argv=[arg.replace(str(case),'<mutated-bundle>') for arg in cmd],returncode=p.returncode,stdout=p.stdout,stderr=p.stderr,rehashed=name!='corruption')
            reports.append(report)
            atomic_json(out/(name+'.json'),report)
            reasons={'forged-feed-freshness':'forged feed freshness','undisclosed-as-fee':'fee replaced an undisclosed amount','future-event-feature':'event-then-future feature leakage','wrong-value-model':'wrong valuation model ID','missing-artifact':'missing required execution artifact','failed-replay':'saved-engine bounded replay differs','corruption':'artifact checksum mismatch','source-mismatch':'source mismatch'}
            if p.returncode==0 or reasons[name] not in p.stderr:raise RuntimeError('negative control failed to reject for its intended semantic reason: '+name)
    result=dict(status='passed',rejected=len(reports),reports=reports)
    atomic_json(out/'REPORT.json',result);return result
