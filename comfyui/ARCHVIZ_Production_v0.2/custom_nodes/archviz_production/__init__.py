"""ARCHVIZ staged local workflow. Models are called inside RUN only."""
import json
import re
from pathlib import Path

import numpy as np
import torch
import folder_paths

from .state_core import PassError, canonical
from .engine import ProductionStore, mask_set, asset_identity, geometry_diagnostic
from . import backends

CATEGORY = 'ARCHVIZ/Production v0.2'
STAGES = ('facade', 'road', 'greenery', 'people', 'upscale')


def store_for(project):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', project):
        raise PassError('Project: use 1-64 ASCII letters, digits, underscore or hyphen')
    return ProductionStore(Path(folder_paths.get_output_directory())/'archviz_production'/project)


def input_path(value):
    if not value.strip():
        return ''
    root = Path(folder_paths.get_input_directory()).resolve()
    path = (root/value).resolve()
    if not path.is_relative_to(root):
        raise PassError('MASK_PATH_OUTSIDE_INPUT')
    return str(path)


def model_names(category, fallback):
    return folder_paths.get_filename_list(category) or [fallback]


def model_identity(category, name):
    path = folder_paths.get_full_path(category, name)
    if not path:
        raise PassError('MODEL_NOT_FOUND: '+category+'/'+name)
    return asset_identity(path)


def record(packet, stage, status, **extra):
    return dict(packet, history=[*packet['history'], dict(stage=stage, status=status, **extra)])


def routed(packet, stage, result):
    brief = {k: v for k, v in result.items() if k not in ('image', 'manifest')}
    packet = record(packet, stage, result['status'], details=brief)
    packet['image'] = result['image']
    if result['status'] in ('SKIPPED', 'CACHED'):
        packet['state_id'] = result['state_id']
    else:
        packet['blocked'] = True
        packet['attempt_id'] = result.get('attempt_id')
        packet['notice'] = ('Review preview, then set MASTER action=ACCEPT or REJECT and target_id=attempt_id. '
                            'After ACCEPT use CACHE for this stage. Change run_nonce to explicitly regenerate.')
    return packet


class Master:
    CATEGORY = CATEGORY
    FUNCTION = 'execute'
    RETURN_TYPES = ('AP_CONTROL',)
    RETURN_NAMES = ('control',)

    @classmethod
    def INPUT_TYPES(cls):
        r = {
            'project': ('STRING', {'default': 'archviz_demo_v02'}),
            'action': (['INSPECT', 'EXECUTE', 'ACCEPT', 'REJECT', 'CHECKOUT'],),
            'target_id': ('STRING', {'default': ''}),
            'reviewed': ('BOOLEAN', {'default': False}),
            'review_note': ('STRING', {'default': '', 'multiline': True}),
            'run_nonce': ('INT', {'default': 1, 'min': 1, 'max': 2147483647}),
            'checkpoint': (model_names('checkpoints', 'RealVisXL_V4.0.safetensors'),
                           {'default': 'RealVisXL_V4.0.safetensors'}),
            'seed': ('INT', {'default': 42001, 'min': 0, 'max': 0xffffffffffffffff}),
        }
        for stage in STAGES:
            r[stage+'_mode'] = (['SKIP', 'RUN', 'CACHE'],)
            r[stage+'_cache_id'] = ('STRING', {'default': ''})
        r['upscale_method'] = (['OFF', 'CONSERVATIVE', 'GENERATIVE'],)
        r['export_final'] = ('BOOLEAN', {'default': False})
        return {'required': r}

    def execute(self, **control):
        return (control,)


class Entry:
    CATEGORY = CATEGORY
    FUNCTION = 'execute'
    RETURN_TYPES = ('AP_STATE',)
    RETURN_NAMES = ('accepted_state',)

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'control': ('AP_CONTROL',), 'original': ('IMAGE',)}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')

    def execute(self, control, original):
        if original.shape[0] != 1:
            raise PassError('Exactly one ORIGINAL image per project')
        s = store_for(control['project'])
        try:
            oid = s.initialize(original[0].detach().cpu().numpy())
            action = control['action']
            sid = oid
            decision = None
            if action in ('ACCEPT', 'REJECT'):
                decision = s.decide(control['target_id'].strip(), action,
                                    control['review_note'], control['reviewed'])
                sid = s.pointer()
            elif action == 'CHECKOUT':
                if not control['reviewed'] or not control['review_note'].strip():
                    raise PassError('CHECKOUT needs reviewed and a note')
                s.checkout(control['target_id'].strip()); sid = s.pointer()
            elif action == 'INSPECT':
                sid = s.pointer()
            image, manifest = s.read(sid, accepted=True)
            return ({'project': control['project'], 'state_id': sid, 'original_id': oid,
                     'image': image, 'blocked': action != 'EXECUTE',
                     'history': [dict(stage='entry', action=action, state_id=sid,
                                      head=s.pointer(), decision_result=decision)],
                     'notice': 'Await explicit EXECUTE' if action != 'EXECUTE' else ''},)
        finally:
            s.close()


class LocalPass:
    CATEGORY = CATEGORY
    FUNCTION = 'execute'
    RETURN_TYPES = ('AP_STATE',)
    RETURN_NAMES = ('state_or_review_candidate',)

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'state': ('AP_STATE',), 'control': ('AP_CONTROL',),
            'stage': (list(STAGES[:4]),),
            'prompt': ('STRING', {'default': 'photorealistic architectural visualization, believable materials', 'multiline': True}),
            'negative': ('STRING', {'default': 'distorted architecture, extra windows, changed geometry, illustration, artifacts', 'multiline': True}),
            'edit_mask': ('STRING', {'default': ''}),
            'protect_mask': ('STRING', {'default': ''}),
            'influence_mask': ('STRING', {'default': ''}),
            'composite_mask': ('STRING', {'default': ''}),
            'steps': ('INT', {'default': 24, 'min': 1, 'max': 100}),
            'cfg': ('FLOAT', {'default': 5., 'min': 0., 'max': 20.}),
            'denoise': ('FLOAT', {'default': .24, 'min': .01, 'max': 1.}),
            'max_side': ('INT', {'default': 1024, 'min': 64, 'max': 2048, 'step': 8}),
            'context_pixels': ('INT', {'default': 96, 'min': 0, 'max': 512}),
            'controlnet': (model_names('controlnet', 'diffusers_xl_canny_full.safetensors'),
                           {'default': 'diffusers_xl_canny_full.safetensors'}),
            'control_strength': ('FLOAT', {'default': .65, 'min': 0., 'max': 2.}),
            'erase_region': ('BOOLEAN', {'default': False}),
        }}

    def execute(self, state, control, stage, edit_mask, protect_mask, influence_mask,
                composite_mask, **settings):
        if state['blocked']:
            return (state,)
        mode = control[stage+'_mode']
        if mode == 'SKIP':
            return (record(state, stage, 'SKIPPED'),)
        paths = {k: input_path(v) for k, v in dict(edit=edit_mask, protect=protect_mask,
                 influence=influence_mask, composite=composite_mask).items()}
        masks = mask_set(paths, state['image'].shape[:2])
        p = dict(settings, backend='sdxl-local-crop/v0.2', checkpoint=control['checkpoint'],
                 seed=(control['seed']+STAGES.index(stage)*1009) % (2**64),
                 checkpoint_identity=model_identity('checkpoints', control['checkpoint']))
        if p['control_strength']:
            p['controlnet_identity'] = model_identity('controlnet', p['controlnet'])
        s = store_for(state['project'])
        try:
            original, _ = s.read(state['original_id'], accepted=True)
            callback = lambda parent, params: backends.sdxl_edit(parent, params, masks, original)
            result = s.local_pass(mode, state['state_id'], masks, p, stage, callback,
                                  control[stage+'_cache_id'], control['run_nonce'])
            return (routed(state, stage, result),)
        finally:
            s.close()


class Upscale:
    CATEGORY = CATEGORY
    FUNCTION = 'execute'
    RETURN_TYPES = ('AP_STATE',)
    RETURN_NAMES = ('state_or_review_candidate',)

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'state': ('AP_STATE',), 'control': ('AP_CONTROL',),
            'scale': ('FLOAT', {'default': 2., 'min': 1., 'max': 4.}),
            'upscale_model': (['Lanczos (no model)']+model_names('upscale_models', 'RealESRGAN_x4plus.safetensors'),),
            'protect_mask': ('STRING', {'default': ''}),
            'prompt': ('STRING', {'default': 'photorealistic architectural photograph, fine natural material detail, preserve architecture', 'multiline': True}),
            'negative': ('STRING', {'default': 'new windows, changed geometry, oversharpening, artifacts', 'multiline': True}),
            'steps': ('INT', {'default': 16, 'min': 1, 'max': 60}),
            'cfg': ('FLOAT', {'default': 4., 'min': 0., 'max': 20.}),
            'denoise': ('FLOAT', {'default': .12, 'min': .01, 'max': .5}),
            'tile_size': ('INT', {'default': 768, 'min': 128, 'max': 1536, 'step': 8}),
            'tile_overlap': ('INT', {'default': 128, 'min': 8, 'max': 256, 'step': 8}),
            'detail_blend': ('FLOAT', {'default': .5, 'min': 0., 'max': 1.}),
        }}

    def execute(self, state, control, protect_mask, **settings):
        if state['blocked']:
            return (state,)
        mode = control['upscale_mode']
        if mode == 'SKIP' or control['upscale_method'] == 'OFF':
            return (record(state, 'upscale', 'SKIPPED'),)
        if settings['tile_overlap'] >= settings['tile_size']:
            raise PassError('tile_overlap must be smaller than tile_size')
        p = dict(settings, backend='upscale-local/v0.2', upscale_mode=control['upscale_method'],
                 checkpoint=control['checkpoint'], seed=(control['seed']+4001) % (2**64))
        if p['upscale_mode'] == 'GENERATIVE':
            p['checkpoint_identity'] = model_identity('checkpoints', p['checkpoint'])
        elif p['upscale_model'] != 'RealESRGAN_x4plus.safetensors':
            p['upscale_model_identity'] = model_identity('upscale_models', p['upscale_model'])
        s = store_for(state['project'])
        try:
            result = s.upscale_pass(mode, state['state_id'], p, backends.upscale,
                                    control['upscale_cache_id'], control['run_nonce'], input_path(protect_mask))
            return (routed(state, 'upscale', result),)
        finally:
            s.close()


class Quality:
    CATEGORY = CATEGORY
    FUNCTION = 'execute'
    RETURN_TYPES = ('AP_STATE',)
    RETURN_NAMES = ('state',)

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'state': ('AP_STATE',), 'label': ('STRING', {'default': 'FINAL CONSISTENCY'})}}

    def execute(self, state, label):
        s = store_for(state['project'])
        try:
            original, _ = s.read(state['original_id'], accepted=True)
            qc = geometry_diagnostic(original, state['image'])
            return (record(state, label, 'REVIEW_REQUIRED', geometry_diagnostic=qc,
                           visual='NOT_EVALUATED', semantic_window_matching='NOT_EVALUATED'),)
        finally:
            s.close()


class Inspector:
    CATEGORY = CATEGORY
    FUNCTION = 'execute'
    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('preview', 'report')
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'state': ('AP_STATE',), 'control': ('AP_CONTROL',)}}

    def execute(self, state, control):
        s = store_for(state['project'])
        try:
            report = {k: v for k, v in state.items() if k != 'image'}
            report.update(current_head=s.pointer(), processor_calls=s.call_count(),
                          storage=str(s.root), dimensions=list(state['image'].shape))
            if control['export_final'] and control['action'] == 'EXECUTE' and not state['blocked']:
                if state['state_id'] != s.pointer():
                    raise PassError('EXPORT_NOT_CURRENT_HEAD: use matching CACHE lineage or CHECKOUT')
                _, m = s.read(state['state_id'], accepted=True)
                report['export'] = {'accepted_bundle': str(s.root/state['state_id']),
                                    'image_hash': m['image_hash'],
                                    'notice': 'image.npy is float32 master; preview.png is 8-bit delivery preview'}
                dest = s.root/('final_'+state['state_id']+'.json')
                if not dest.exists():
                    with dest.open('x', encoding='utf-8') as f:
                        f.write(json.dumps(report, ensure_ascii=False, indent=2))
            text = json.dumps(report, ensure_ascii=False, indent=2)
            return {'ui': {'text': [text]}, 'result': (torch.from_numpy(state['image'].copy()).unsqueeze(0), text)}
        finally:
            s.close()


NODE_CLASS_MAPPINGS = {'APMasterControl': Master, 'APOriginalState': Entry,
                       'APLocalPass': LocalPass, 'APUpscalePass': Upscale,
                       'APQualityReview': Quality, 'APInspector': Inspector}
NODE_DISPLAY_NAME_MAPPINGS = {'APMasterControl': 'ARCHVIZ · MASTER / Decisions',
    'APOriginalState': 'ARCHVIZ · Immutable Original / State',
    'APLocalPass': 'ARCHVIZ · Processor + Composite + QC',
    'APUpscalePass': 'ARCHVIZ · Upscale / Composite / QC',
    'APQualityReview': 'ARCHVIZ · Reference Contour Diagnostic',
    'APInspector': 'ARCHVIZ · Inspector / Accepted Export'}
