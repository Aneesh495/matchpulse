"""Import authorized local StatsBomb files through the ordinary normalized engine."""
from pathlib import Path
import argparse
import json
import sys
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from matchpulse.adapters import bounded_json,statsbomb_archive
from matchpulse.storage import Store
from matchpulse.engine import Engine
from matchpulse.resources import guard
p=argparse.ArgumentParser();p.add_argument('--events',type=Path,required=True);p.add_argument('--lineups',type=Path,required=True);p.add_argument('--metadata',type=Path,required=True);p.add_argument('--rights',type=Path,required=True);p.add_argument('--acquired-at',required=True);p.add_argument('--db',default='runtime/matchpulse.db');a=p.parse_args()
guard(root,100_000_000)
result=statsbomb_archive(bounded_json(a.events),bounded_json(a.lineups),json.loads(a.metadata.read_text()),json.loads(a.rights.read_text()),a.acquired_at)
s=Store(a.db);e=Engine(s)
try:
    e.seed(result['packet'])
    for event in result['events']:e.ingest(event)
    print(json.dumps(dict(imported=len(result['events']),skipped=result['skipped'],warning=result['warning'])))
finally:s.close()
