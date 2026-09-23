import argparse, json, shutil, time
from demo_assets import ensure_assets
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--lab', default=r'C:\ComfyUI-Installs\ARCHVIZ_LAB\ComfyUI')
p.add_argument('--shared-input', default='')
args=p.parse_args()

source=Path(__file__).resolve().parent
lab=Path(args.lab).resolve()
if not (lab/'main.py').is_file():
    raise SystemExit('STOP: ComfyUI main.py not found: '+str(lab))

custom=lab/'custom_nodes'
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
if dst.exists():
    snap=backup_root/f'archviz_production_before_variant01_{time.strftime("%Y%m%d_%H%M%S")}'
    shutil.copytree(dst,snap)
    shutil.rmtree(dst)
dst.mkdir(parents=True)
for f in (source/'custom_nodes'/'archviz_production').glob('*.py'):
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

wf=source/'workflows'/'ARCHVIZ_Production_VARIANT_01.json'
wd=lab/'user'/'default'/'workflows'/wf.name
wd.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(wf,wd)

report={
 'status':'PASS',
 'lab':str(lab),
 'moved_active_backups':moved,
 'active_custom_node':str(dst),
 'workflow':str(wd),
 'input_targets':[str(x) for x in targets],
 'restart_required':True,
 'generation_models_changed':False,
 'python_packages_changed':False,
}
report_text=json.dumps(report,ensure_ascii=False,indent=2)
try:
    report_path=source/'INSTALL_REPORT.json'
    report_path.write_text(report_text,encoding='utf-8')
except OSError:
    report_path=lab/'user'/'ARCHVIZ_VARIANT_01_INSTALL_REPORT.json'
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(report_text,encoding='utf-8')
report['report_path']=str(report_path)
print(json.dumps(report,ensure_ascii=False,indent=2))
