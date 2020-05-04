"""Project-attributable bytes and actual Data volume use before predictable growth."""
from __future__ import annotations
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from .contracts import ContractError

PROJECT_LIMIT=5_000_000_000
MAC_LIMIT=400_000_000_000


def inventory(root:Path)->dict:
    root=root.resolve()
    for parent in root.parents:
        module=parent/'go.mod'
        if module.is_file() and 'github.com/Aneesh495/matchpulse-football' in module.read_text():
            root=parent
    def bytes_under(directory:Path)->tuple[int,int]:
        total=0;files=0
        for base,_,names in os.walk(directory):
            for name in names:
                p=Path(base)/name
                if p.is_symlink():continue
                try:total+=p.stat().st_size;files+=1
                except FileNotFoundError:pass
        return total,files
    total,files=bytes_under(root)
    local=total;shared=[]
    caches=[Path(os.environ.get('npm_config_cache',str(Path.home()/'.npm')))]
    go_cache=os.environ.get('GOCACHE')
    if not go_cache:
        try:go_cache=subprocess.check_output(['go','env','GOCACHE'],text=True,timeout=5).strip()
        except (OSError,subprocess.SubprocessError):go_cache=None
    if go_cache and go_cache!='off':caches.append(Path(go_cache))
    for cache in caches:
        if cache.exists() and not cache.resolve().is_relative_to(root):
            size,count=bytes_under(cache);total+=size;files+=count
            shared.append(dict(path=str(cache),bytes=size,policy='entire shared cache conservatively reserved'))
    volume=Path('/System/Volumes/Data') if platform.system()=='Darwin' else root
    disk=shutil.disk_usage(volume)
    return dict(project_bytes=total,local_project_bytes=local,project_files=files,shared_cache_reservations=shared,
        volume_used_bytes=disk.used,volume_free_bytes=disk.free,project_limit=PROJECT_LIMIT,volume_limit=MAC_LIMIT,
        accounting='outer project checkout including nested clean checks, Git, dependencies, data and evidence; entire npm and Go shared caches conservatively reserved')


def guard(root:Path,reserve:int=0)->dict:
    measured=inventory(root)
    if measured['project_bytes']+reserve>PROJECT_LIMIT:raise ContractError("project storage budget exceeded")
    if platform.system()=='Darwin' and measured['volume_used_bytes']+reserve>MAC_LIMIT:raise ContractError("Mac-used budget exceeded")
    if reserve>measured['volume_free_bytes']:raise ContractError("insufficient storage for reservation")
    return measured


def doctor(root:Path)->dict:
    def version(command):
        try:return subprocess.check_output(command,text=True,stderr=subprocess.STDOUT,timeout=5).strip()
        except (OSError,subprocess.SubprocessError):return "unavailable"
    return dict(platform=platform.platform(),architecture=platform.machine(),cpus=os.cpu_count(),python=sys.version,
        go=version(['go','version']),node=version(['node','--version']),
        storage=inventory(root),precision="IEEE-754 binary64 Python float",gpu="not used; CPU diagnostic only",
        actual_datasets=sorted(str(p) for p in (root/'data').glob('*/manifest.json')),
        live_credentials="not configured",full_profile="blocked")
