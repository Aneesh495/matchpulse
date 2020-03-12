from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from matchpulse.negative_controls import controls
root=Path.cwd();(root/'.agent-local').mkdir(exist_ok=True)
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
result=controls(Path(sys.argv[1]),root,commit,root/'evidence'/sys.argv[2])
print(result['status'],result['rejected'])
