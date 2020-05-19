"""Check local prose links, diagram rendering and forbidden punctuation."""
from pathlib import Path
from collections import Counter
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];errors=[]
for p in [root/'README.md',root/'CONTRIBUTING.md',*root.glob('docs/**/*.md')]:
    text=p.read_text()
    if '\u2014' in text:errors.append(f'{p}: forbidden punctuation')
    for link in re.findall(r'\]\(([^)]+)\)',text):
        if link.startswith(('https://','http://','#','mailto:')):continue
        target=(p.parent/link.split('#')[0]).resolve()
        if not target.exists():errors.append(f'{p}: missing link {link}')
try:
    graphviz=json.loads(subprocess.check_output(['node','scripts/render-diagrams.mjs'],cwd=root))
except Exception as exc:
    print(f'pinned Graphviz rendering failed: {exc}',file=sys.stderr);sys.exit(1)
for p in root.glob('docs/diagrams/*.dot'):
    svg=p.with_suffix('.svg')
    try:
        ET.parse(svg)
        rendered=graphviz['graphs'][p.name]
        expected=ET.fromstring(rendered);existing=ET.parse(svg).getroot()
        labels=lambda element:[n.text for n in element.iter() if n.tag.endswith('}text')]
        if Counter(labels(expected))!=Counter(labels(existing)):errors.append(f'{p}: stale diagram labels')
    except Exception as exc:errors.append(str(exc))
if len(list(root.glob('docs/diagrams/*.dot')))<12:errors.append('missing architecture diagram coverage')
for err in errors:print(err,file=sys.stderr)
print(f'documentation checks: {len(errors)} failures; Graphviz {graphviz["graphviz"]}')
sys.exit(bool(errors))
