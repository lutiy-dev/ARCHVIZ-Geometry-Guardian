"""ARCHVIZ staged local workflow. Models are called inside RUN only."""
import json
import re
from pathlib import Path

import numpy as np
import torch
import folder_paths

from .state_core import PassError, canonical, array_hash, digest, image_array
from .engine import ProductionStore, mask_set, load_mask, asset_identity, geometry_diagnostic
from . import backends

CATEGORY = 'ARCHVIZ/Production VARIANT 02'
STAGES = ('facade', 'road', 'greenery', 'people', 'upscale')


WORKSPACE_META_KEY = 'archviz_workspace_id'


def _workflow_namespace(extra_pnginfo):
    payload = extra_pnginfo or {}
    workflow = payload.get('workflow', payload) if isinstance(payload, dict) else {}
    extra = workflow.get('extra', {}) if isinstance(workflow, dict) else {}
    value = extra.get(WORKSPACE_META_KEY, '') if isinstance(extra, dict) else ''
    if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{8,96}', value):
        return value
    return 'api_fallback'


def workspace_key(original, extra_pnginfo=None):
    a = image_array(original)
    original_hash = array_hash(a)
    namespace = _workflow_namespace(extra_pnginfo)
    key = 'w_' + digest((namespace + '|' + original_hash).encode('utf-8'))
    return key, original_hash, namespace


def store_for(workspace):
    if not re.fullmatch(r'w_[0-9a-f]{64}', workspace):
        raise PassError('INVALID_INTERNAL_WORKSPACE')
    return ProductionStore(Path(folder_paths.get_output_directory())/'archviz_production'/'variant_02'/workspace)


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
        return {
            'required': {'control': ('AP_CONTROL',), 'original': ('IMAGE',)},
            'hidden': {'extra_pnginfo': 'EXTRA_PNGINFO'},
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')

    def execute(self, control, original, extra_pnginfo=None):
        if original.shape[0] != 1:
            raise PassError('Exactly one ORIGINAL image is required')
        original_np = original[0].detach().cpu().numpy()
        workspace, original_hash, namespace = workspace_key(original_np, extra_pnginfo)
        s = store_for(workspace)
        try:
            oid = s.initialize(original_np)
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
            return ({'workspace': workspace, 'workspace_namespace': namespace,
                     'original_hash': original_hash, 'state_id': sid, 'original_id': oid,
                     'image': image, 'blocked': action != 'EXECUTE',
                     'history': [dict(stage='entry', action=action, state_id=sid,
                                      head=s.pointer(), decision_result=decision)],
                     'notice': 'Await explicit EXECUTE' if action != 'EXECUTE' else ''},)
        finally:
            s.close()


class StateImage:
    """Expose the current stage parent image from AP_STATE for sequential mask generation."""
    CATEGORY = CATEGORY
    FUNCTION = 'execute'
    RETURN_TYPES = ('IMAGE',)
    RETURN_NAMES = ('image',)

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'state': ('AP_STATE',)}}

    def execute(self, state):
        image = image_array(state['image'])
        return (torch.from_numpy(image.copy()).unsqueeze(0),)



def _mask_tensor_to_np(mask, shape, binary=False):
    if mask is None:
        return np.zeros(shape, np.float32)
    if isinstance(mask, torch.Tensor):
        a = mask.detach().float().cpu().numpy()
    else:
        a = np.asarray(mask, dtype=np.float32)
    while a.ndim > 2:
        a = a[0]
    if a.shape != tuple(shape):
        raise PassError(f'MASK_SIZE_MISMATCH_DIRECT: got {a.shape}, expected {tuple(shape)}')
    a = np.clip(a.astype(np.float32), 0.0, 1.0)
    return (a >= .5).astype(np.float32) if binary else a


def _maskset(edit, protect, influence, composite, source):
    alpha = composite * np.maximum(edit, influence) * (1.0 - protect)
    empty = not np.any(alpha > 0)
    if empty and source != 'AUTO':
        raise PassError('EMPTY_EFFECTIVE_MASK: inspect Mask Preview / source')
    return {
        'source': source,
        'status': 'EMPTY' if empty else 'READY',
        'edit': edit.astype(np.float32),
        'protect': protect.astype(np.float32),
        'influence': influence.astype(np.float32),
        'composite': composite.astype(np.float32),
    }


class AutoMaskSet:
    """Convert one semantic AUTO mask into the production EDIT/PROTECT/INFLUENCE/COMPOSITE contract."""
    CATEGORY = CATEGORY
    FUNCTION = 'execute'
    RETURN_TYPES = ('AP_MASKSET',)
    RETURN_NAMES = ('maskset',)

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'reference_image': ('IMAGE',),
            'auto_edit': ('MASK',),
        }}

    def execute(self, reference_image, auto_edit):
        if reference_image.shape[0] != 1:
            raise PassError('AUTO_MASK_REQUIRES_SINGLE_REFERENCE_IMAGE')
        shape = tuple(reference_image.shape[1:3])
        edit = _mask_tensor_to_np(auto_edit, shape, True)
        protect = np.zeros(shape, np.float32)
        influence = np.zeros(shape, np.float32)
        composite = edit.copy()
        return (_maskset(edit, protect, influence, composite, 'AUTO'),)


class PreparedMaskSet:
    """Load a complete PREPARED mask contract from ComfyUI input/ by path.

    EDIT is required. PROTECT and INFLUENCE may be blank (zero).
    COMPOSITE may be blank (falls back to max(EDIT, INFLUENCE)).
    """
    CATEGORY = CATEGORY
    FUNCTION = 'execute'
    RETURN_TYPES = ('AP_MASKSET',)
    RETURN_NAMES = ('maskset',)

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'reference_image': ('IMAGE',),
            'edit_path': ('STRING', {'default': 'archviz_demo_v02/facade_edit.png'}),
            'protect_path': ('STRING', {'default': ''}),
            'influence_path': ('STRING', {'default': ''}),
            'composite_path': ('STRING', {'default': ''}),
        }}

    def execute(self, reference_image, edit_path, protect_path, influence_path, composite_path):
        if reference_image.shape[0] != 1:
            raise PassError('PREPARED_MASK_REQUIRES_SINGLE_REFERENCE_IMAGE')
        shape = tuple(reference_image.shape[1:3])
        if not edit_path.strip():
            raise PassError('PREPARED_EDIT_PATH_REQUIRED')
        paths = {
            'edit': input_path(edit_path),
            'protect': input_path(protect_path) if protect_path.strip() else '',
            'influence': input_path(influence_path) if influence_path.strip() else '',
            'composite': input_path(composite_path) if composite_path.strip() else '',
        }
        masks = mask_set(paths, shape)
        return (_maskset(masks['edit'], masks['protect'], masks['influence'], masks['composite'], 'PREPARED'),)


class MaskSourceSwitch:
    """Pass-aware lazy AUTO/PREPARED switch. SKIP/CACHE do not execute mask branches."""
    CATEGORY = CATEGORY
    FUNCTION = 'execute'
    RETURN_TYPES = ('AP_MASKSET', 'MASK', 'MASK', 'MASK', 'MASK')
    RETURN_NAMES = ('maskset', 'edit_preview', 'protect_preview', 'influence_preview', 'composite_preview')

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'source': (['AUTO', 'PREPARED'],),
            'control': ('AP_CONTROL',),
            'state': ('AP_STATE',),
            'stage': (list(STAGES[:4]),),
            'auto_maskset': ('AP_MASKSET', {'lazy': True}),
            'prepared_maskset': ('AP_MASKSET', {'lazy': True}),
        }}

    def check_lazy_status(self, source, control, state, stage,
                          auto_maskset=None, prepared_maskset=None):
        if state.get('blocked') or control[stage+'_mode'] != 'RUN':
            return []
        if source == 'AUTO' and auto_maskset is None:
            return ['auto_maskset']
        if source == 'PREPARED' and prepared_maskset is None:
            return ['prepared_maskset']
        return []

    def execute(self, source, control, state, stage,
                auto_maskset=None, prepared_maskset=None):
        mode = control[stage+'_mode']
        if state.get('blocked') or mode != 'RUN':
            shape = tuple(image_array(state['image']).shape[:2])
            z = np.zeros(shape, np.float32)
            chosen = {
                'source': 'BYPASS',
                'status': mode,
                'edit': z.copy(),
                'protect': z.copy(),
                'influence': z.copy(),
                'composite': z.copy(),
            }
        else:
            chosen = auto_maskset if source == 'AUTO' else prepared_maskset
            if chosen is None:
                raise PassError(f'{source}_MASKSET_MISSING')

        def t(a):
            return torch.from_numpy(np.asarray(a, dtype=np.float32).copy()).unsqueeze(0)

        return (chosen, t(chosen['edit']), t(chosen['protect']),
                t(chosen['influence']), t(chosen['composite']))

class LocalPass:
    CATEGORY = CATEGORY
    FUNCTION = 'execute'
    RETURN_TYPES = ('AP_STATE',)
    RETURN_NAMES = ('state_or_review_candidate',)

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'state': ('AP_STATE',), 'control': ('AP_CONTROL',),
            'maskset': ('AP_MASKSET', {'lazy': True}),
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

    def check_lazy_status(self, state, control, maskset=None, stage='facade', **kwargs):
        if state.get('blocked'):
            return []
        if control[stage+'_mode'] != 'RUN':
            return []
        return ['maskset'] if maskset is None else []

    def execute(self, state, control, maskset, stage, edit_mask, protect_mask, influence_mask,
                composite_mask, **settings):
        if state['blocked']:
            return (state,)
        mode = control[stage+'_mode']
        if mode == 'SKIP':
            return (record(state, stage, 'SKIPPED'),)

        # CACHE is intentionally mask-engine-free. Explicit cache_id is required so
        # reuse is deliberate and no current AUTO/PREPARED branch must be evaluated.
        if mode == 'CACHE':
            cache_id = control[stage+'_cache_id'].strip()
            if not cache_id:
                raise PassError('CACHE_ID_REQUIRED: CACHE bypasses Mask Engine; select an accepted cache state')
            s = store_for(state['workspace'])
            try:
                cached, manifest = s.read(cache_id, accepted=True)
                if manifest.get('parent_state_id') != state['state_id']:
                    raise PassError('STALE_PARENT')
                if manifest.get('pass_id') != stage:
                    raise PassError('CACHE_PASS_MISMATCH')
                result = {'status': 'CACHED', 'state_id': cache_id, 'image': cached, 'manifest': manifest}
                return (routed(state, stage, result),)
            finally:
                s.close()

        if maskset is None:
            raise PassError('RUN_REQUIRES_MASKSET')
        if maskset.get('source') == 'AUTO' and maskset.get('status') == 'EMPTY':
            return (record(state, stage, 'SKIPPED_EMPTY_MASK',
                           mask_source='AUTO', reason='NO_TARGET_DETECTED'),)

        masks = {k: np.asarray(maskset[k], dtype=np.float32) for k in ('edit','protect','influence','composite')}
        expected = tuple(state['image'].shape[:2])
        if any(masks[k].shape != expected for k in masks):
            raise PassError('MASKSET_SIZE_MISMATCH')
        p = dict(settings, backend='sdxl-local-crop/v0.2', checkpoint=control['checkpoint'],
                 seed=(control['seed']+STAGES.index(stage)*1009) % (2**64),
                 checkpoint_identity=model_identity('checkpoints', control['checkpoint']))
        if p['control_strength']:
            p['controlnet_identity'] = model_identity('controlnet', p['controlnet'])
        s = store_for(state['workspace'])
        try:
            original, _ = s.read(state['original_id'], accepted=True)
            callback = lambda parent, params: backends.sdxl_edit(parent, params, masks, original)
            result = s.local_pass('RUN', state['state_id'], masks, p, stage, callback,
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
        elif p['upscale_model'] != 'Lanczos (no model)':
            p['upscale_model_identity'] = model_identity('upscale_models', p['upscale_model'])
        s = store_for(state['workspace'])
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
        s = store_for(state['workspace'])
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
        s = store_for(state['workspace'])
        try:
            report = {k: v for k, v in state.items() if k != 'image'}
            report.update(current_head=s.pointer(), processor_calls=s.call_count(),
                          storage=str(s.root), dimensions=list(state['image'].shape))
            if control['export_final'] and control['action'] == 'EXECUTE' and not state['blocked']:
                if state['state_id'] != s.pointer():
                    raise PassError('EXPORT_NOT_CURRENT_HEAD: use matching CACHE lineage or CHECKOUT')
                # Immutable state bundle already contains lossless float image, preview and manifest.
                _, m = s.read(state['state_id'], accepted=True)
                report['export'] = {'accepted_bundle': str(s.root/state['state_id']),
                                    'image_hash': m['image_hash'],
                                    'notice': 'image.npy is float32 master; preview.png is 8-bit delivery preview'}
                # Revision-specific filename; repeated export is idempotent.
                dest = s.root/('final_'+state['state_id']+'.json')
                if not dest.exists():
                    with dest.open('x', encoding='utf-8') as f:
                        f.write(json.dumps(report, ensure_ascii=False, indent=2))
            text = json.dumps(report, ensure_ascii=False, indent=2)
            return {'ui': {'text': [text]}, 'result': (torch.from_numpy(state['image'].copy()).unsqueeze(0), text)}
        finally:
            s.close()


NODE_CLASS_MAPPINGS = {
    'APMasterControl': Master,
    'APOriginalState': Entry,
    'APStateImage': StateImage,
    'APAutoMaskSet': AutoMaskSet,
    'APPreparedMaskSet': PreparedMaskSet,
    'APMaskSourceSwitch': MaskSourceSwitch,
    'APLocalPass': LocalPass,
    'APUpscalePass': Upscale,
    'APQualityReview': Quality,
    'APInspector': Inspector,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'APMasterControl': 'ARCHVIZ · MASTER / Decisions',
    'APOriginalState': 'ARCHVIZ · Auto Workspace / Immutable Original',
    'APStateImage': 'ARCHVIZ · Current Stage Image',
    'APAutoMaskSet': 'ARCHVIZ · AUTO Mask Contract',
    'APPreparedMaskSet': 'ARCHVIZ · PREPARED Mask Contract',
    'APMaskSourceSwitch': 'ARCHVIZ · Mask Source Switch / Preview',
    'APLocalPass': 'ARCHVIZ · Processor + Composite + QC',
    'APUpscalePass': 'ARCHVIZ · Upscale / Composite / QC',
    'APQualityReview': 'ARCHVIZ · Reference Contour Diagnostic',
    'APInspector': 'ARCHVIZ · Inspector / Accepted Export',
}
