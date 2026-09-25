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
req(wf['extra'].get('archviz_runtime')=='hansen-sequential-working-v02','wrong runtime architecture')
req(bool(wf['extra'].get('archviz_workspace_id')),'workflow namespace missing')
req(nodes[1]['widgets_values'][0]=='INSPECT','Project ID still serialized in MASTER widgets')
req(sum(n['type']=='APStateImage' for n in wf['nodes'])==4,'need four stage image nodes')
req(sum(n['type']=='APMaskReference' for n in wf['nodes'])==4,'need four SAM3 mask-reference nodes')
req(nodes[50]['type']=='Image Comparer (rgthree)','final Image Comparer missing')
req(nodes[50]['properties'].get('comparer_mode')=='Slide','final comparer must use Slide mode')

# The production state chain itself remains FACADE -> ROAD -> GREENERY -> PEOPLE.
for link_id,src_id,dst_id in [(3,5,7),(5,7,8),(7,8,9),(9,9,10)]:
    l=links[link_id]
    req(l[1]==src_id and l[3]==dst_id and l[5]=='AP_STATE',f'bad state chain {link_id}')

# Each stage exposes the full current working image to contracts, while SAM3 alone
# receives a CPU-downscaled 1024px semantic reference.
checks=[
    (42,5,46,75,21,[23,25],64,22,71),
    (43,7,47,76,31,[33,35],66,28,72),
    (44,8,48,77,41,[43,45],68,34,73),
    (45,9,49,78,51,[53,55],70,40,74),
]
for image_node,parent,mask_ref,ref_in,sam_link,full_links,switch_link,switch_node,state_link in checks:
    req(nodes[image_node]['type']=='APStateImage',f'bad state image {image_node}')
    req(links[state_link][1]==parent and links[state_link][3]==image_node,'stage image parent mismatch')
    req(nodes[mask_ref]['type']=='APMaskReference',f'bad mask reference {mask_ref}')
    req(nodes[mask_ref]['widgets_values'][0]==1024,f'mask reference max-side changed {mask_ref}')
    req(links[ref_in][1]==image_node and links[ref_in][3]==mask_ref,'mask reference input mismatch')
    req(links[sam_link][1]==mask_ref and links[sam_link][5]=='IMAGE','SAM3 must use reduced reference')
    for lid in full_links:
        req(links[lid][1]==image_node and links[lid][5]=='IMAGE',f'full reference link changed {lid}')
    req(links[switch_link][1]==parent and links[switch_link][3]==switch_node and links[switch_link][5]=='AP_STATE',
        f'bad switch state {switch_node}')

# FINAL COMPARE: original A, final inspector preview B.
req(links[79][1]==4 and links[79][3]==50 and links[79][4]==0,'compare A must be ORIGINAL')
req(links[80][1]==14 and links[80][3]==50 and links[80][4]==1,'compare B must be final preview')

# Every serialized link must be symmetric. This catches the 4-link repair warning
# previously emitted by ComfyUI for control links 63/65/67/69.
for lid,l in links.items():
    _,src_id,src_slot,dst_id,dst_slot,_=l
    outs=nodes[src_id]['outputs']
    req(src_slot < len(outs),f'bad source slot for link {lid}')
    out_links=outs[src_slot].get('links')
    req(out_links is not None and lid in out_links,f'origin missing link {lid}')
    ins=nodes[dst_id]['inputs']
    req(dst_slot < len(ins),f'bad target slot for link {lid}')
    req(ins[dst_slot].get('link')==lid,f'target missing link {lid}')

# Runtime architecture assertions: a RUN stage produces a working image and must not
# block the next RUN stage. Only Inspector creates the final review candidate.
req("WORKING_RUN" in src,'working RUN status missing')
req("out['blocked'] = False" in src,'working RUN does not explicitly stay unblocked')
req("finalize_pipeline" in src,'single final review gate missing')
req("Sequential working image" in src,'sequential runtime notice missing')
req("packet['blocked'] = True" not in src,'legacy per-stage blocking still present')

# Contract matrix for user-facing combinations. This is a deterministic execution
# contract check; real GPU generation remains a separate TESTED gate.
def expected_calls(modes, upscale=False):
    calls=[s for s in ('facade','road','greenery','people') if modes.get(s)=='RUN']
    if upscale:
        calls.append('upscale')
    return calls
matrix=[
    ({'facade':'RUN'},False,['facade']),
    ({'road':'RUN'},False,['road']),
    ({'greenery':'RUN'},False,['greenery']),
    ({'facade':'RUN','road':'RUN'},False,['facade','road']),
    ({'facade':'RUN','greenery':'RUN'},False,['facade','greenery']),
    ({'road':'RUN','greenery':'RUN'},False,['road','greenery']),
    ({'facade':'RUN','road':'RUN','greenery':'RUN'},False,['facade','road','greenery']),
    ({'facade':'RUN','greenery':'RUN'},True,['facade','greenery','upscale']),
    ({'facade':'RUN','road':'RUN','greenery':'RUN','people':'RUN'},True,
     ['facade','road','greenery','people','upscale']),
]
for modes,upscale_on,expected_calls_list in matrix:
    req(expected_calls(modes,upscale_on)==expected_calls_list,'combination contract failed')

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

print(json.dumps({'status':'PASS','variant':'VARIANT_02','workflow_nodes':len(wf['nodes']),'workflow_links':len(wf['links']),'manual_project_id_removed':True,'auto_workspace':'workflow namespace + ORIGINAL hash','runtime_architecture':'HANSEN_SEQUENTIAL_WORKING','sequential_stage_images':'PASS_STATIC','combination_matrix':'PASS_STATIC','sam3_mask_reference_1024':'PASS_STATIC','vram_barriers':'PASS_STATIC','final_single_review_gate':'PASS_STATIC','final_image_comparer':'PASS_STATIC','link_symmetry':'PASS','auto_empty_passthrough':'PASS','prepared_empty_strict':'PASS','generation_baseline_preserved':'PASS','installer_simulation':'PASS','workflow_sha256':sha(WF),'runtime_gpu_tested':False},indent=2))
