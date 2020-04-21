"""Package exact tracked source plus built UI. This is not a full research release."""
from pathlib import Path
import argparse
import io
import json
import subprocess
import tarfile
import sys
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from matchpulse.resources import guard
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
guard(root,50_000_000)
if subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=root).returncode:raise SystemExit('commit source changes before packaging')
if not (root/'dist/index.html').exists():raise SystemExit('run make build first')
a.output.parent.mkdir(parents=True,exist_ok=True)
files=subprocess.check_output(['git','ls-files'],cwd=root,text=True).splitlines()
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
with tarfile.open(a.output,'x:gz') as archive:
    for name in files:
        if name.startswith(('.agent-local/','data/','runtime/','evidence/')):raise SystemExit('restricted path in tracked source')
        archive.add(root/name,arcname='matchpulse/'+name,recursive=False)
    for path in (root/'dist').rglob('*'):
        if path.is_file():archive.add(path,arcname='matchpulse/'+str(path.relative_to(root)),recursive=False)
    content=json.dumps(dict(kind='diagnostic-source-package',source_commit=commit,full_acceptance='blocked'),sort_keys=True).encode()
    info=tarfile.TarInfo('matchpulse/PACKAGE.json');info.size=len(content);archive.addfile(info,io.BytesIO(content))
print(a.output.resolve())
