import sys, types, tempfile, shutil, json, importlib.util
from pathlib import Path
import numpy as np, torch
from demo_assets import ensure_assets

ROOT=Path(__file__).resolve().parent
TMP=Path(tempfile.mkdtemp(prefix='archviz_variant01_test_'))
try:
    inp=TMP/'input'; out=TMP/'output'; inp.mkdir(); out.mkdir()
    ensure_assets(inp)

    fp=types.ModuleType('folder_paths')
    fp.get_input_directory=lambda: str(inp)
    fp.get_output_directory=lambda: str(out)
    fp.get_filename_list=lambda c: {
        'checkpoints':['RealVisXL_V4.0.safetensors'],
        'controlnet':['diffusers_xl_canny_full.safetensors'],
        'upscale_models':['RealESRGAN_x4plus.safetensors'],
    }.get(c,[])
    fp.get_full_path=lambda c,n: str(TMP/(c+'_'+n))
    for c,n in [('checkpoints','RealVisXL_V4.0.safetensors'),('controlnet','diffusers_xl_canny_full.safetensors'),('upscale_models','RealESRGAN_x4plus.safetensors')]:
        (TMP/(c+'_'+n)).write_bytes(b'x')
    sys.modules['folder_paths']=fp

    package='archviz_production_test'
    spec=importlib.util.spec_from_file_location(package, ROOT/'custom_nodes'/'archviz_production'/'__init__.py',
                                                submodule_search_locations=[str(ROOT/'custom_nodes'/'archviz_production')])
    mod=importlib.util.module_from_spec(spec); sys.modules[package]=mod; spec.loader.exec_module(mod)

    wf=json.loads((ROOT/'workflows'/'ARCHVIZ_Production_VARIANT_01.json').read_text(encoding='utf-8'))
    ids=[n['id'] for n in wf['nodes']]
    assert len(ids)==len(set(ids)), 'duplicate node ids'
    lids=[l[0] for l in wf['links']]
    assert len(lids)==len(set(lids)), 'duplicate link ids'
    assert not [n for n in wf['nodes'] if n['type']=='LoadImage' and 'PREPARED' in n.get('title','')], 'prepared media LoadImage remains'
    assert len([n for n in wf['nodes'] if n['type']=='APMaskSourceSwitch'])==4
    assert len([n for n in wf['nodes'] if n['type']=='APPreparedMaskSet'])==4
    assert len([n for n in wf['nodes'] if n['type']=='APAutoMaskSet'])==4

    # Synthetic reference using bundled image dimensions from one mask.
    from PIL import Image
    m=np.asarray(Image.open(inp/'archviz_demo_v02'/'facade_edit.png').convert('L'),dtype=np.float32)/255
    h,w=m.shape
    ref=torch.zeros((1,h,w,3),dtype=torch.float32)

    prep=mod.PreparedMaskSet().execute(ref,'archviz_demo_v02/facade_edit.png',
        'archviz_demo_v02/facade_protect.png','',
        'archviz_demo_v02/facade_composite.png')[0]
    assert prep['source']=='PREPARED' and prep['edit'].shape==(h,w)
    auto=mod.AutoMaskSet().execute(ref,torch.from_numpy(m).unsqueeze(0))[0]
    assert auto['source']=='AUTO' and auto['status']=='READY'
    empty_auto=mod.AutoMaskSet().execute(ref,torch.zeros((1,h,w),dtype=torch.float32))[0]
    assert empty_auto['source']=='AUTO' and empty_auto['status']=='EMPTY'
    sw=mod.MaskSourceSwitch()

    # State entry persistence: same original/project is allowed twice.
    control=mod.Master().execute(project='archviz_variant01_selftest',action='EXECUTE',target_id='',reviewed=False,
        review_note='',run_nonce=1,checkpoint='RealVisXL_V4.0.safetensors',seed=42001,
        facade_mode='SKIP',facade_cache_id='',road_mode='SKIP',road_cache_id='',
        greenery_mode='SKIP',greenery_cache_id='',people_mode='SKIP',people_cache_id='',
        upscale_mode='SKIP',upscale_cache_id='',upscale_method='OFF',export_final=False)[0]
    state1=mod.Entry().execute(control,ref)[0]
    state2=mod.Entry().execute(control,ref)[0]
    assert state1['original_id']==state2['original_id']
    # SKIP: neither mask source nor LocalPass requires SAM3/masks.
    assert sw.check_lazy_status('AUTO',control,ref,'facade',None,None)==[]
    bypass=sw.execute('AUTO',control,ref,'facade',None,None)[0]
    assert bypass['source']=='BYPASS' and bypass['status']=='SKIP'
    lp=mod.LocalPass().execute(state1,control,None,'facade','','','','',
        steps=24,cfg=5.0,denoise=.24,max_side=1024,context_pixels=96,
        controlnet='diffusers_xl_canny_full.safetensors',control_strength=.65,erase_region=False)[0]
    assert lp['history'][-1]['status']=='SKIPPED'

    # RUN + empty AUTO is a valid no-target passthrough.
    control_run=dict(control); control_run['facade_mode']='RUN'
    assert sw.check_lazy_status('AUTO',control_run,ref,'facade',None,None)==['auto_maskset']
    no_target=mod.LocalPass().execute(state1,control_run,empty_auto,'facade','','','','',
        steps=24,cfg=5.0,denoise=.24,max_side=1024,context_pixels=96,
        controlnet='diffusers_xl_canny_full.safetensors',control_strength=.65,erase_region=False)[0]
    assert no_target['history'][-1]['status']=='SKIPPED_EMPTY_MASK'
    assert no_target['history'][-1]['reason']=='NO_TARGET_DETECTED'

    print('SELF_TEST: PASS')
    print(f'workflow_nodes={len(wf["nodes"])} links={len(wf["links"])}')
    print('prepared_media_inputs=0')
    print('lazy_switches=4')
    print('state_repeat_same_original=PASS')
    print('localpass_skip=PASS')
    print('pass_aware_mask_bypass=PASS')
    print('empty_auto_passthrough=PASS')
finally:
    shutil.rmtree(TMP,ignore_errors=True)
