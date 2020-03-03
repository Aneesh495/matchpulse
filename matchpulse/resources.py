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
    total=0;files=0
    for directory,_,names in os.walk(root):
        for name in names:
            p=Path(directory)/name
            if p.is_symlink():continue
            try:total+=p.stat().st_size;files+=1
            except FileNotFoundError:pass
    volume=Path('/System/Volumes/Data') if platform.system()=='Darwin' else root
    disk=shutil.disk_usage(volume)
    return dict(project_bytes=total,project_files=files,volume_used_bytes=disk.used,volume_free_bytes=disk.free,
        project_limit=PROJECT_LIMIT,volume_limit=MAC_LIMIT,
        accounting="checkout, Git, local dependencies, raw inputs, evidence, runtime and nested clean checks; no shared project cache used")


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
