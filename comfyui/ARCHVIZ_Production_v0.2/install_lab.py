"""Additive installer: no package changes, model moves, overwrites or process restarts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from generate_demo_assets import ensure_demo_assets

parser=argparse.ArgumentParser()
parser.add_argument('--lab',default=r'C:\ComfyUI-Installs\ARCHVIZ_LAB\ComfyUI')
args=parser.parse_args()
source=Path(__file__).resolve().parent
lab=Path(args.lab).resolve()
if not (lab/'main.py').is_file() or not (lab/'custom_nodes').is_dir():
    raise SystemExit('Not a verified ComfyUI installation: '+str(lab))

# Repo is self-contained for smoke testing: create deterministic demo input/masks
# when binary demo assets are not present in the checkout.
ensure_demo_assets(source)

files=[]
for p in (source/'custom_nodes/archviz_production').glob('*.py'):
    files.append((p,lab/'custom_nodes/archviz_production'/p.name))
for p in (source/'input/archviz_demo_v02').glob('*.png'):
    files.append((p,lab/'input/archviz_demo_v02'/p.name))
files.append((source/'input/archviz_demo_v02_original.png',lab/'input/archviz_demo_v02_original.png'))
files.append((source/'workflows/ARCHVIZ_Production_v02.json',lab/'user/default/workflows/ARCHVIZ_Production_v02.json'))
files.append((source/'README_RU.md',lab/'custom_nodes/archviz_production/README_RU.md'))

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

for src,dst in files:
    if not dst.resolve().is_relative_to(lab): raise SystemExit('Destination escapes LAB')
    if dst.exists() and sha(src)!=sha(dst):
        raise SystemExit('Refusing to overwrite existing different file: '+str(dst))

report=[]
for src,dst in files:
    exists=dst.exists()
    if not exists:
        dst.parent.mkdir(parents=True,exist_ok=True)
        with src.open('rb') as inp,dst.open('xb') as out: shutil.copyfileobj(inp,out)
    if sha(src)!=sha(dst): raise SystemExit('Copy verification failed: '+str(dst))
    report.append({'destination':str(dst),'sha256':sha(dst),'action':'unchanged' if exists else 'created'})

result={'lab':str(lab),'restart_required':True,'restart_performed':False,'model_files_changed':0,
        'python_packages_changed':0,'demo_assets_generated':True,'files':report}
(source/'installation-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'verified_files':len(report),'restart_required':True,'lab':str(lab),
                  'demo_assets':'ready'},ensure_ascii=False))
