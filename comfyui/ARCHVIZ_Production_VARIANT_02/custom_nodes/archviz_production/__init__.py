"""ARCHVIZ staged local workflow. Models are called inside RUN only."""
import json
import re
from pathlib import Path

import numpy as np
import torch
import folder_paths

from .state_core import PassError, canonical, array_hash, digest, image_array, composite, local_qc
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
            # Every new EXECUTE starts from the current accepted head, not from ORIGINAL.
            # This preserves previously ACCEPTED work while ORIGINAL remains immutable truth.
            sid = s.pointer() or oid
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
                     'original_hash': original_hash, 'state_id': sid, 'base_state_id': sid,
                     'original_id': oid, 'working_dirty': False,
                     'image': image, 'blocked': action != 'EXECUTE',
                     'history': [dict(stage='entry', action=action, state_id=sid,
                                      head=s.pointer(), decision_result=decision)],
                     'notice': 'Await explicit EXECUTE' if action != 'EXECUTE' else ''},)
        finally:
            s.close()


def _release_vram():
    """Best-effort model offload between SAM3 and SDXL/ESRGAN stages.

    This does not change model/settings; it only releases inactive GPU allocations.
    """
    try:
        import comfy.model_management as mm
        if hasattr(mm, 'unload_all_models'):
            mm.unload_all_models()
        if hasattr(mm, 'soft_empty_cache'):
            mm.soft_empty_cache()
    except Exception:
        # Memory cleanup must never turn a valid pass into a hard failure.
        pass


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



class MaskReference:
    """CPU resize used only for semantic detection; production image stays full-resolution."""
    CATEGORY = CATEGORY
    FUNCTION = 'execute'
    RETURN_TYPES = ('IMAGE',)
    RETURN_NAMES = ('image',)

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'image': ('IMAGE',),
            'max_side': ('INT', {'default': 1024, 'min': 512, 'max': 2048, 'step': 64}),
        }}

    def execute(self, image, max_side):
        if image.shape[0] != 1:
            raise PassError('MASK_REFERENCE_REQUIRES_SINGLE_IMAGE')
        a = image[0].detach().float().cpu().numpy()
        h, w = a.shape[:2]
        scale = min(1.0, float(max_side) / max(h, w))
        if scale >= 1.0:
            return (image,)
        nw = max(8, int(round(w * scale / 8.0)) * 8)
        nh = max(8, int(round(h * scale / 8.0)) * 8)
        resized = backends.resize_float(a, nw, nh)
        return (torch.from_numpy(resized.copy()).unsqueeze(0),)


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
        if isinstance(auto_edit, torch.Tensor):
            edit = auto_edit.detach().float().cpu().numpy()
        else:
            edit = np.asarray(auto_edit, dtype=np.float32)
        while edit.ndim > 2:
            edit = edit[0]
        if edit.shape != shape:
            edit = backends.resize_float(edit.astype(np.float32), shape[1], shape[0], True)
        edit = (np.clip(edit, 0.0, 1.0) >= .5).astype(np.float32)
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
        if state.get('blocked'):
            return (state,)
        mode = control[stage+'_mode']
        if mode == 'SKIP':
            return (record(state, stage, 'SKIPPED'),)

        # Legacy accepted-state CACHE remains available only before any working RUN.
        # Hansen-style execution normally uses RUN/SKIP through the whole chain.
        if mode == 'CACHE':
            if state.get('working_dirty'):
                raise PassError('CACHE_AFTER_WORKING_RUN_UNSUPPORTED: use RUN or SKIP in sequential mode')
            cache_id = control[stage+'_cache_id'].strip()
            if not cache_id:
                raise PassError('CACHE_ID_REQUIRED')
            s = store_for(state['workspace'])
            try:
                cached, manifest = s.read(cache_id, accepted=True)
                if manifest.get('pass_id') != stage:
                    raise PassError('CACHE_PASS_MISMATCH')
                out = record(state, stage, 'CACHED', cache_id=cache_id)
                out['image'] = cached
                out['state_id'] = cache_id
                out['base_state_id'] = cache_id
                return (out,)
            finally:
                s.close()

        if maskset is None:
            raise PassError('RUN_REQUIRES_MASKSET')
        if maskset.get('source') == 'AUTO' and maskset.get('status') == 'EMPTY':
            return (record(state, stage, 'SKIPPED_EMPTY_MASK',
                           mask_source='AUTO', reason='NO_TARGET_DETECTED'),)

        masks = {k: np.asarray(maskset[k], dtype=np.float32)
                 for k in ('edit','protect','influence','composite')}
        parent = image_array(state['image'])
        expected = tuple(parent.shape[:2])
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
            s.event('PROCESSOR_CALLED', {'stage': stage, 'profile': p['backend'],
                                         'working_parent_hash': array_hash(parent)})
            _release_vram()  # SAM3 no longer needs to occupy VRAM while SDXL runs.
            try:
                raw = backends.sdxl_edit(parent, p, masks, original)
                out_image, alpha = composite(parent, raw, masks)
            except Exception as e:
                s.event('PROCESSOR_FAILED', {'stage': stage, 'error': str(e)})
                raise
            finally:
                _release_vram()  # Make room for the next stage's SAM3.
            qc = local_qc(parent, out_image, masks, alpha)
            qc['geometry_diagnostic'] = geometry_diagnostic(original, out_image)
            out = record(state, stage, 'WORKING_RUN',
                         mask_source=maskset.get('source'),
                         result_hash=array_hash(out_image), qc=qc)
            out['image'] = out_image
            out['working_dirty'] = True
            out['blocked'] = False
            out['notice'] = 'Sequential working image; final ACCEPT/REJECT happens after the full chain.'
            return (out,)
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
        if state.get('blocked'):
            return (state,)
        mode = control['upscale_mode']
        if mode == 'SKIP' or control['upscale_method'] == 'OFF':
            return (record(state, 'upscale', 'SKIPPED'),)
        if mode == 'CACHE':
            if state.get('working_dirty'):
                raise PassError('UPSCALE_CACHE_AFTER_WORKING_RUN_UNSUPPORTED: use RUN')
            cache_id = control['upscale_cache_id'].strip()
            if not cache_id:
                raise PassError('CACHE_ID_REQUIRED')
            s = store_for(state['workspace'])
            try:
                cached, manifest = s.read(cache_id, accepted=True)
                out = record(state, 'upscale', 'CACHED', cache_id=cache_id)
                out['image'] = cached
                out['state_id'] = cache_id
                out['base_state_id'] = cache_id
                return (out,)
            finally:
                s.close()
        if settings['tile_overlap'] >= settings['tile_size']:
            raise PassError('tile_overlap must be smaller than tile_size')

        parent = image_array(state['image'])
        p = dict(settings, backend='upscale-local/v0.2',
                 upscale_mode=control['upscale_method'],
                 checkpoint=control['checkpoint'],
                 seed=(control['seed']+4001) % (2**64))
        if p['upscale_mode'] == 'GENERATIVE':
            p['checkpoint_identity'] = model_identity('checkpoints', p['checkpoint'])
        elif p['upscale_model'] != 'Lanczos (no model)':
            p['upscale_model_identity'] = model_identity('upscale_models', p['upscale_model'])

        s = store_for(state['workspace'])
        try:
            s.event('PROCESSOR_CALLED', {'stage': 'upscale', 'profile': p['backend'],
                                         'working_parent_hash': array_hash(parent)})
            _release_vram()
            try:
                candidate = image_array(backends.upscale(parent, p))
            except Exception as e:
                s.event('PROCESSOR_FAILED', {'stage': 'upscale', 'error': str(e)})
                raise
            finally:
                _release_vram()

            h, w = parent.shape[:2]
            baseline = backends.resize_float(parent, round(w*p['scale']), round(h*p['scale']))
            if candidate.shape != baseline.shape:
                raise PassError('INVALID_UPSCALE_DIMENSIONS')
            protect = load_mask(input_path(protect_mask), (h, w), True) if protect_mask.strip() else np.zeros((h,w), np.float32)
            protect = backends.resize_float(protect, baseline.shape[1], baseline.shape[0], True)
            blend = p['detail_blend'] if p['upscale_mode'] == 'GENERATIVE' else 1.0
            alpha = np.full(baseline.shape[:2], blend, np.float32) * (1-protect)
            out_image = baseline.copy()
            active = alpha > 0
            a = alpha[active, None]
            out_image[active] = baseline[active]*(1-a) + candidate[active]*a
            original, _ = s.read(state['original_id'], accepted=True)
            qc = local_qc(baseline, out_image, {'protect': protect}, alpha)
            qc['geometry_diagnostic'] = geometry_diagnostic(original, out_image)
            out = record(state, 'upscale', 'WORKING_RUN',
                         result_hash=array_hash(out_image), qc=qc)
            out['image'] = out_image
            out['working_dirty'] = True
            out['blocked'] = False
            out['notice'] = 'Sequential working image; final ACCEPT/REJECT happens after the full chain.'
            return (out,)
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
            preview = image_array(state['image'])
            if control['action'] == 'EXECUTE' and not state.get('blocked') and state.get('working_dirty'):
                final = s.finalize_pipeline(state['base_state_id'], preview,
                                            state['history'], control['run_nonce'])
                preview = final['image']
                report.update(final_status=final['status'],
                              attempt_id=final.get('attempt_id'),
                              final_request_key=final.get('request_key'),
                              reused_attempt=final.get('reused_attempt', False),
                              notice='Review final pipeline candidate, then ACCEPT or REJECT once.')
            elif control['action'] == 'EXECUTE' and not state.get('working_dirty'):
                report.update(final_status='NO_CHANGES',
                              notice='No RUN stage changed the accepted image; no candidate created.')

            report.update(current_head=s.pointer(), processor_calls=s.call_count(),
                          storage=str(s.root), dimensions=list(preview.shape))

            if control['export_final'] and control['action'] != 'EXECUTE':
                sid = s.pointer()
                _, m = s.read(sid, accepted=True)
                report['export'] = {'accepted_bundle': str(s.root/sid),
                                    'image_hash': m['image_hash'],
                                    'notice': 'image.npy is float32 master; preview.png is 8-bit delivery preview'}

            text = json.dumps(report, ensure_ascii=False, indent=2)
            return {'ui': {'text': [text]},
                    'result': (torch.from_numpy(preview.copy()).unsqueeze(0), text)}
        finally:
            s.close()


NODE_CLASS_MAPPINGS = {
    'APMasterControl': Master,
    'APOriginalState': Entry,
    'APStateImage': StateImage,
    'APMaskReference': MaskReference,
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
    'APMaskReference': 'ARCHVIZ · SAM3 Mask Reference (Downscale)',
    'APAutoMaskSet': 'ARCHVIZ · AUTO Mask Contract',
    'APPreparedMaskSet': 'ARCHVIZ · PREPARED Mask Contract',
    'APMaskSourceSwitch': 'ARCHVIZ · Mask Source Switch / Preview',
    'APLocalPass': 'ARCHVIZ · Processor + Composite + QC',
    'APUpscalePass': 'ARCHVIZ · Upscale / Composite / QC',
    'APQualityReview': 'ARCHVIZ · Reference Contour Diagnostic',
    'APInspector': 'ARCHVIZ · Inspector / Accepted Export',
}
