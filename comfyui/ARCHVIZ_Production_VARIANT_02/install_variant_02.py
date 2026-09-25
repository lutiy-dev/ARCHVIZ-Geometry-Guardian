import argparse, hashlib, json, shutil, time
from demo_assets import ensure_assets
from pathlib import Path

VARIANT = "VARIANT_02"
WORKFLOW = "ARCHVIZ_Production_VARIANT_02.json"

def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

p=argparse.ArgumentParser()
p.add_argument('--lab', default=r'C:\ComfyUI-Installs\ARCHVIZ_LAB\ComfyUI')
p.add_argument('--shared-input', default='')
args=p.parse_args()

source=Path(__file__).resolve().parent
lab=Path(args.lab).resolve()
if not (lab/'main.py').is_file():
    raise SystemExit('STOP: ComfyUI main.py not found: '+str(lab))

custom=lab/'custom_nodes'
custom.mkdir(parents=True,exist_ok=True)
backup_root=lab.parent/'_DISABLED_NODE_BACKUPS'
backup_root.mkdir(parents=True,exist_ok=True)

moved=[]
for pat in ('archviz_production_backup*','archviz_production_old*'):
    for d in list(custom.glob(pat)):
        if not d.is_dir():
            continue
        target=backup_root/d.name
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(d),str(target))
        moved.append(str(target))

dst=custom/'archviz_production'
snapshot=None
if dst.exists():
    snapshot=backup_root/f'archviz_production_before_variant02_{time.strftime("%Y%m%d_%H%M%S")}'
    shutil.copytree(dst,snapshot)
    shutil.rmtree(dst)
dst.mkdir(parents=True)

src_node=source/'custom_nodes'/'archviz_production'
for f in src_node.glob('*.py'):
    shutil.copy2(f,dst/f.name)

targets=[lab/'input']
if args.shared_input:
    targets.append(Path(args.shared_input))
else:
    auto=Path.home()/'AppData'/'Local'/'Comfy-Desktop'/'ComfyUI-Shared'/'input'
    if auto.parent.exists():
        targets.append(auto)
for target in targets:
    ensure_assets(target)

wf=source/'workflows'/WORKFLOW
if not wf.is_file():
    raise SystemExit('STOP: workflow missing: '+str(wf))
wd=lab/'user'/'default'/'workflows'/wf.name
wd.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(wf,wd)

if sha256(wf) != sha256(wd):
    raise SystemExit('STOP: installed workflow hash mismatch')
for f in src_node.glob('*.py'):
    if sha256(f) != sha256(dst/f.name):
        raise SystemExit('STOP: installed custom-node hash mismatch: '+f.name)

report={
 'status':'PASS','variant':VARIANT,'lab':str(lab),
 'snapshot':str(snapshot) if snapshot else None,
 'moved_active_backups':moved,'active_custom_node':str(dst),'workflow':str(wd),
 'workflow_sha256':sha256(wd),'input_targets':[str(x) for x in targets],
 'restart_required':True,'manual_project_id_removed':True,
 'workspace_strategy':'workflow namespace + ORIGINAL hash',
 'generation_models_changed':False,'python_packages_changed':False,
}
report_path=lab/'user'/'ARCHVIZ_VARIANT_02_INSTALL_REPORT.json'
report_path.parent.mkdir(parents=True,exist_ok=True)
report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
report['report_path']=str(report_path)
print(json.dumps(report,ensure_ascii=False,indent=2))
