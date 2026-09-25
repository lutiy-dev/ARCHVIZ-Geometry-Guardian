"""Local SDXL backends; imports and model loading happen only inside RUN."""
from functools import lru_cache
import numpy as np


@lru_cache(maxsize=1)
def checkpoint(name, fingerprint=''):
    import nodes
    return nodes.CheckpointLoaderSimple().load_checkpoint(name)


@lru_cache(maxsize=1)
def controlnet(name, fingerprint=''):
    import nodes
    return nodes.ControlNetLoader().load_controlnet(name)[0]


def resize_float(a, width, height, nearest=False):
    import cv2
    return cv2.resize(a, (width, height), interpolation=cv2.INTER_NEAREST if nearest else cv2.INTER_LANCZOS4).clip(0, 1).astype(np.float32)


def sdxl_edit(parent, parameters, masks, original):
    import torch
    import nodes
    import cv2
    from .state_core import PassError
    allowed = np.maximum(masks['edit'], masks['influence']) * (1-masks['protect'])
    ys, xs = np.where((allowed * masks['composite']) > 0)
    if not len(xs):
        raise PassError('EMPTY_EDIT_REGION: no model loaded')
    h, w = parent.shape[:2]
    pad = parameters['context_pixels']
    x0, x1 = max(0, int(xs.min())-pad), min(w, int(xs.max())+pad+1)
    y0, y1 = max(0, int(ys.min())-pad), min(h, int(ys.max())+pad+1)
    crop = parent[y0:y1, x0:x1]
    scale = min(1., parameters['max_side']/max(crop.shape[:2]))
    cw = max(64, int(round(crop.shape[1]*scale/8))*8)
    ch = max(64, int(round(crop.shape[0]*scale/8))*8)
    pixels = torch.from_numpy(resize_float(crop, cw, ch)).unsqueeze(0)
    mask = torch.from_numpy(resize_float(allowed[y0:y1, x0:x1], cw, ch, True)).unsqueeze(0)
    model, clip, vae = checkpoint(parameters['checkpoint'], str(parameters.get('checkpoint_identity', '')))
    with torch.inference_mode():
        positive = nodes.CLIPTextEncode().encode(clip, parameters['prompt'])[0]
        negative = nodes.CLIPTextEncode().encode(clip, parameters['negative'])[0]
        if parameters['control_strength'] > 0:
            ref = resize_float(original[y0:y1, x0:x1], cw, ch)
            gray = cv2.cvtColor(np.rint(ref*255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, 100, 200).astype(np.float32)/255
            hint = torch.from_numpy(np.repeat(edges[..., None], 3, axis=2)).unsqueeze(0)
            positive, negative = nodes.ControlNetApplyAdvanced().apply_controlnet(
                positive, negative, controlnet(parameters['controlnet'], str(parameters.get('controlnet_identity', ''))), hint,
                parameters['control_strength'], 0., .85, vae=vae)
        if parameters.get('erase_region', False):
            latent = nodes.VAEEncodeForInpaint().encode(vae, pixels, mask, grow_mask_by=0)[0]
        else:
            latent = nodes.VAEEncode().encode(vae, pixels)[0]
            latent['noise_mask'] = mask
        result = nodes.KSampler().sample(model, parameters['seed'], parameters['steps'],
            parameters['cfg'], 'dpmpp_2m', 'karras', positive, negative, latent,
            denoise=parameters['denoise'])[0]
        decoded = nodes.VAEDecode().decode(vae, result)[0][0].detach().float().cpu().numpy()
    out = parent.copy()
    out[y0:y1, x0:x1] = resize_float(decoded, x1-x0, y1-y0)
    return out


def upscale(parent, p):
    """Conservative = Lanczos/ESRGAN; Generative = overlap-tiled SDXL detail."""
    import torch
    h, w = parent.shape[:2]
    width, height = round(w*p['scale']), round(h*p['scale'])
    baseline = resize_float(parent, width, height)
    if p['upscale_mode'] == 'CONSERVATIVE':
        if p['upscale_model'] == 'Lanczos (no model)':
            return baseline
        from comfy_extras.nodes_upscale_model import UpscaleModelLoader, ImageUpscaleWithModel
        with torch.inference_mode():
            model = UpscaleModelLoader.execute(p['upscale_model'])[0]
            result = ImageUpscaleWithModel.execute(model, torch.from_numpy(parent).unsqueeze(0))[0]
        return resize_float(result[0].detach().float().cpu().numpy(), width, height)
    tile, overlap = p['tile_size'], p['tile_overlap']
    if not 0 <= overlap < tile:
        raise ValueError('Invalid tile overlap')
    def positions(n):
        return sorted(set(list(range(0, max(n-tile, 0)+1, tile-overlap))+[max(n-tile, 0)]))
    total = np.zeros_like(baseline)
    weights = np.zeros((height, width), np.float32)
    for yi, y in enumerate(positions(height)):
        for xi, x in enumerate(positions(width)):
            import comfy.model_management
            comfy.model_management.throw_exception_if_processing_interrupted()
            patch = baseline[y:y+tile, x:x+tile]
            ph, pw = patch.shape[:2]
            ones, zeros = np.ones((ph, pw), np.float32), np.zeros((ph, pw), np.float32)
            params = dict(p, context_pixels=0, max_side=tile, control_strength=0.,
                          erase_region=False, seed=(p['seed']+yi*10007+xi) % (2**63-1))
            candidate = sdxl_edit(patch, params, dict(edit=ones, influence=zeros,
                                  protect=zeros, composite=ones), patch)
            weight = np.maximum(np.hanning(ph), .03)[:, None] * np.maximum(np.hanning(pw), .03)[None, :]
            total[y:y+ph, x:x+pw] += candidate*weight[..., None]
            weights[y:y+ph, x:x+pw] += weight
    return np.clip(total/weights[..., None], 0, 1).astype(np.float32)
