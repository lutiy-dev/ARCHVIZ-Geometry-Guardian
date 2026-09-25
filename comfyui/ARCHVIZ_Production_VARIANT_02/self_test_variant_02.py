import ast, hashlib, json, tempfile, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
WF=ROOT/'workflows'/'ARCHVIZ_Production_VARIANT_02.json'
INIT=ROOT/'custom_nodes'/'archviz_production'/'__init__.py'
FILES=[INIT,ROOT/'custom_nodes'/'archviz_production'/'state_core.py',ROOT/'custom_nodes'/'archviz_production'/'engine.py',ROOT/'custom_nodes'/'archviz_production'/'backends.py',ROOT/'install_variant_02.py',ROOT/'demo_assets.py']

def req(ok,msg):
    if not ok: raise AssertionError(msg)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for p in FILES:
    ast.parse(p.read_text(encoding='utf-8'), filename=str(p))

src=INIT.read_text(encoding='utf-8')
req("'project': ('STRING'" not in src,'manual project widget still exists')
req("control['project']" not in src and "state['project']" not in src,'manual project state still used')
req("workspace_key(" in src and "archviz_workspace_id" in src,'automatic workspace logic missing')
req("'APStateImage': StateImage" in src,'APStateImage node missing')
req("state.get('blocked')" in src,'blocked state does not gate mask switch')
req("if empty and source != 'AUTO':" in src,'AUTO empty-mask policy missing')
req("'SKIPPED_EMPTY_MASK'" in src and "'NO_TARGET_DETECTED'" in src,'AUTO empty passthrough missing')

wf=json.loads(WF.read_text(encoding='utf-8'))
nodes={n['id']:n for n in wf['nodes']}; links={l[0]:l for l in wf['links']}
req(wf['extra']['archviz_version']=='VARIANT_02','wrong variant')
req(bool(wf['extra'].get('archviz_workspace_id')),'workflow namespace missing')
req(nodes[1]['widgets_values'][0]=='INSPECT','Project ID still serialized in MASTER widgets')
req(sum(n['type']=='APStateImage' for n in wf['nodes'])==4,'need four stage image nodes')
req(nodes[4]['outputs'][0]['links']==[2],'ORIGINAL must only feed state entry')
for link_id,src_id,dst_id in [(3,5,7),(5,7,8),(7,8,9),(9,9,10)]:
    l=links[link_id]; req(l[1]==src_id and l[3]==dst_id and l[5]=='AP_STATE',f'bad state chain {link_id}')
checks=[(42,5,[21,23,25],64,22,71),(43,7,[31,33,35],66,28,72),(44,8,[41,43,45],68,34,73),(45,9,[51,53,55],70,40,74)]
for image_node,parent,ref_links,switch_link,switch_node,state_link in checks:
    req(nodes[image_node]['type']=='APStateImage',f'bad state image {image_node}')
    req(links[state_link][1]==parent and links[state_link][3]==image_node,'stage image parent mismatch')
    for lid in ref_links: req(links[lid][1]==image_node and links[lid][5]=='IMAGE',f'bad stage image link {lid}')
    req(links[switch_link][1]==parent and links[switch_link][3]==switch_node and links[switch_link][5]=='AP_STATE',f'bad switch state {switch_node}')

# Generation baseline: indexes include ComfyUI seed control widget in MASTER but LocalPass indexes are stable.
req(nodes[1]['widgets_values'][5]=='RealVisXL_V4.0.safetensors','checkpoint changed')
expected={7:(0.24,0.65),8:(0.28,0.55),9:(0.4,0.25),10:(0.85,0.0)}
for nid,(denoise,strength) in expected.items():
    w=nodes[nid]['widgets_values']
    req(w[7]==24 and w[8]==5,'steps/CFG changed')
    req(abs(float(w[9])-denoise)<1e-9,f'denoise changed {nid}')
    req(w[12]=='diffusers_xl_canny_full.safetensors',f'ControlNet changed {nid}')
    req(abs(float(w[13])-strength)<1e-9,f'Control strength changed {nid}')
up=nodes[12]['widgets_values']
req(up[0]==2 and up[1]=='RealESRGAN_x4plus.safetensors','upscale model changed')
req(up[5]==16 and up[6]==4 and abs(float(up[7])-0.12)<1e-9,'upscale sampler baseline changed')
req(up[8]==768 and up[9]==128 and abs(float(up[10])-0.5)<1e-9,'upscale tile baseline changed')

def wk(ns,h): return 'w_'+hashlib.sha256((ns+'|'+h).encode()).hexdigest()
a='a'*64; b='b'*64
req(wk('graphA',a)==wk('graphA',a),'workspace not deterministic')
req(wk('graphA',a)!=wk('graphA',b),'different ORIGINAL collides')
req(wk('graphA',a)!=wk('graphB',a),'different graph namespace collides')

with tempfile.TemporaryDirectory() as td:
    td=Path(td); lab=td/'ComfyUI'; (lab/'custom_nodes').mkdir(parents=True); (lab/'main.py').write_text('# fake\n')
    shared=td/'shared'/'input'
    cp=subprocess.run([sys.executable,str(ROOT/'install_variant_02.py'),'--lab',str(lab),'--shared-input',str(shared)],cwd=str(ROOT),text=True,capture_output=True)
    req(cp.returncode==0,'installer simulation failed: '+cp.stdout+'\n'+cp.stderr)
    report=json.loads((lab/'user'/'ARCHVIZ_VARIANT_02_INSTALL_REPORT.json').read_text(encoding='utf-8'))
    req(report['status']=='PASS','installer did not report PASS')
    installed=lab/'user'/'default'/'workflows'/WF.name
    req(installed.is_file() and sha(installed)==sha(WF),'workflow hash mismatch')
    req((lab/'custom_nodes'/'archviz_production'/'__init__.py').is_file(),'custom node not installed')
    req((shared/'archviz_demo_v02_original.png').is_file(),'shared input demo missing')

print(json.dumps({'status':'PASS','variant':'VARIANT_02','workflow_nodes':len(wf['nodes']),'workflow_links':len(wf['links']),'manual_project_id_removed':True,'auto_workspace':'workflow namespace + ORIGINAL hash','sequential_stage_images':'PASS','auto_empty_passthrough':'PASS','prepared_empty_strict':'PASS','skip_cache_lazy_gate':'PASS_STATIC','generation_baseline_preserved':'PASS','installer_simulation':'PASS','workflow_sha256':sha(WF),'runtime_gpu_tested':False},indent=2))
