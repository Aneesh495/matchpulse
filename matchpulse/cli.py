"""Reproducible commands with distinct diagnostic and full profiles."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .contracts import ContractError,canonical,identifier
from .storage import Store
from .engine import Engine
from .demo import packet,deliveries,later_deal,MATCH_ID
from .resources import doctor,guard
from .training import train_diagnostic
from .campaign import campaign


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['doctor','demo','import','ingest','replay','train','acceptance','valuation-audit','bench','data','release'])
    p.add_argument('--db',default='runtime/matchpulse.db');p.add_argument('--input',type=Path)
    p.add_argument('--resume',action='store_true');p.add_argument('--stop-after-epochs',type=int);p.add_argument('--run-id');p.add_argument('--profile',default='diagnostic',choices=['diagnostic','full']);p.add_argument('--speed',type=float,default=20)
    a=p.parse_args();root=Path.cwd()
    try:
        if a.command=='doctor':print(canonical(doctor(root)));return
        guard(root,30_000_000)
        if a.command=='import':
            if a.input is None or a.input.stat().st_size > 10_000_000:
                raise ContractError('import requires an input packet no larger than 10 MB')
            s=Store(a.db)
            try:
                result=Engine(s).seed(json.loads(a.input.read_text()),publish_context=True)
                print(canonical(result))
            finally:s.close()
            return
        if a.command=='train':
            if a.stop_after_epochs is not None and not 1<=a.stop_after_epochs<=42:raise ContractError('stop-after-epochs must be between 1 and 42')
            if a.resume and not a.run_id:raise ContractError('resume requires --run-id')
            rid=identifier(a.run_id or time.strftime('train-%Y%m%d-%H%M%S'))
            report=train_diagnostic(root/'evidence'/rid,resume=a.resume,interrupt_after_epochs=a.stop_after_epochs);print(canonical(report));return
        if a.command in {'acceptance','bench'}:
            if not a.run_id:raise ContractError('--run-id is required; evidence directories never collide')
            rid=identifier(a.run_id);report=campaign(root,root/'evidence'/rid,a.profile)
            print(canonical(report));sys.exit(0 if report['status']=='passed' else 2)
        if a.command=='data':
            print(canonical(dict(status='blocked',reason='No authorized corpus configured. See docs/DATA_RIGHTS.md. No automatic scraping or paid acquisition.')));sys.exit(2)
        if a.command=='release':
            print(canonical(dict(status='blocked',reason='Full research acceptance and implementation requirements remain incomplete. Use scripts/package.py for a diagnostic source archive.')));sys.exit(2)
        if a.command=='valuation-audit':
            from .valuation import Deal
            if a.input:
                rows=json.loads(a.input.read_text())['records']
                for row in rows:Deal.parse(row)
                print(canonical(dict(status='passed',records=len(rows),scope='schema invariants only')))
            else:
                d=Deal.parse(later_deal());print(canonical(dict(status='passed',scope='synthetic demonstration only',target='guaranteed conditional consideration',guaranteed=d.guaranteed,addons_upper=d.addons_upper)))
            return
        s=Store(':memory:' if a.command=='demo' else a.db);engine=Engine(s);engine.seed(packet())
        try:
            events=[json.loads(line) for line in a.input.read_text().splitlines()] if a.input else deliveries()
            if a.command=='replay' and a.speed<=0:raise ContractError('positive replay speed required')
            for i,event in enumerate(events):
                if a.command=='replay' and i:
                    delay=max(0,event['second']-events[i-1]['second'])/a.speed
                    if delay>60:raise ContractError('single replay wait exceeds 60 seconds; use higher speed or ingest')
                    time.sleep(delay)
                result=engine.ingest(event)
                if a.command=='demo':print(canonical(dict(event=event['event_id'],version=result.get('version'),score=result['snapshot']['score'],corrections=len(result['snapshot']['corrections']))))
            if a.command=='demo':engine.deal(later_deal())
            print(canonical(engine.snapshot()))
        finally:s.close()
    except (ContractError,FileExistsError,ValueError,OSError) as exc:
        print(canonical(dict(status='failed',reason=str(exc))),file=sys.stderr);sys.exit(1)


if __name__=='__main__':main()
