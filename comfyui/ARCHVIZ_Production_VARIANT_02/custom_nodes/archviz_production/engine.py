import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image

from .state_core import Store, PassError, array_hash, canonical, digest, image_array, local_qc
from .backends import resize_float


def load_mask(path, shape, binary):
    if not path:
        return np.zeros(shape, np.float32)
    p = Path(path)
    if not p.is_file():
        raise PassError('MASK_NOT_FOUND: '+str(p))
    with Image.open(p) as im:
        a = np.asarray(im.convert('L'), dtype=np.float32)/255
    if a.shape != shape:
        raise PassError('MASK_SIZE_MISMATCH: '+str(p))
    return (a >= .5).astype(np.float32) if binary else a


def mask_set(paths, shape):
    m = {k: load_mask(paths.get(k, ''), shape, k != 'composite')
         for k in ('edit', 'influence', 'protect', 'composite')}
    if not paths.get('composite'):
        m['composite'] = np.maximum(m['edit'], m['influence'])
    return m


def geometry_diagnostic(reference, image):
    import cv2
    h, w = image.shape[:2]
    ref = resize_float(reference, w, h) if reference.shape != image.shape else reference
    max_side = 1024
    scale = min(1., max_side/max(h, w))
    def edges(a):
        a = resize_float(a, max(8, round(w*scale)), max(8, round(h*scale)))
        return cv2.Canny(cv2.cvtColor(np.rint(a*255).astype(np.uint8), cv2.COLOR_RGB2GRAY), 100, 200)>0
    a, b = edges(ref), edges(image)
    if a.sum() < 20 or b.sum() < 20:
        return {'status': 'NOT_EVALUATED', 'reason': 'Insufficient contour evidence', 'coverage': 0}
    da = cv2.distanceTransform((~a).astype(np.uint8), cv2.DIST_L2, 3)
    db = cv2.distanceTransform((~b).astype(np.uint8), cv2.DIST_L2, 3)
    distances = np.concatenate([db[a], da[b]])/scale
    return {'status': 'REVIEW_REQUIRED', 'method': 'symmetric_canny_distance',
            'median_px': float(np.median(distances)), 'p95_px': float(np.percentile(distances, 95)),
            'reference_edges': int(a.sum()), 'result_edges': int(b.sum()),
            'window_identity': 'NOT_EVALUATED', 'coverage': 'edge pixels only',
            'limitation': 'Lighting/material edges can change these metrics; not geometry truth.'}


def asset_identity(path):
    p = Path(path)
    st = p.stat()
    return {'path': str(p.resolve()), 'bytes': st.st_size, 'mtime_ns': st.st_mtime_ns,
            'identity_method': 'path_size_mtime; not full weight hash'}


class ProductionStore(Store):
    def assess(self, parent, out, masks, alpha):
        qc = local_qc(parent, out, masks, alpha)
        original, _ = self.read(self.pointer('original'), accepted=True)
        qc['geometry_diagnostic'] = geometry_diagnostic(original, out)
        return qc

    def __init__(self, root):
        super().__init__(root)
        self.db.execute('CREATE TABLE IF NOT EXISTS requests(key TEXT PRIMARY KEY, artifact TEXT, status TEXT NOT NULL)')
        self.db.commit()

    def prior_attempt(self, key, nonce):
        token = digest((key+'|'+str(nonce)).encode())
        row = self.db.execute('SELECT artifact,status FROM requests WHERE key=?', (token,)).fetchone()
        if not row:
            return token, None
        if not row[0]:
            raise PassError('INCOMPLETE_REQUEST: inspect failure and change run_nonce for an explicit retry')
        image, m = self.read(row[0])
        return token, {'status': m['current_status'], 'attempt_id': row[0], 'image': image,
                       'qc': m['qc'], 'request_key': key, 'reused_attempt': True,
                       'processor_calls': self.call_count()}

    def reserve(self, token):
        with self.db:
            self.db.execute('INSERT INTO requests VALUES (?,NULL,?)', (token, 'RUNNING'))

    def bind(self, token, artifact):
        with self.db:
            self.db.execute('UPDATE requests SET artifact=?,status=? WHERE key=?', (artifact, 'COMPLETE', token))

    def auto_cache(self, key):
        rows = self.db.execute("SELECT id FROM records WHERE kind='state' AND status='ACCEPTED' ORDER BY rowid DESC").fetchall()
        for (sid,) in rows:
            m = json.loads((self.root/sid/'manifest.json').read_text(encoding='utf-8'))
            if m.get('request_key') == key:
                self.read(sid, accepted=True)
                return sid
        raise PassError('INVALID_CACHE: no accepted result matching this parent, model, masks and settings')

    def local_pass(self, mode, parent_id, masks, params, pass_id, processor, cache_id, nonce):
        parent, normalized, request, key = self.request(parent_id, masks, params['backend'], params, pass_id)
        if mode == 'CACHE':
            cache_id = cache_id.strip() or self.auto_cache(key)
        if mode != 'RUN':
            return self.route(mode, parent_id, masks, params['backend'], params,
                              cache_id=cache_id, pass_id=pass_id)
        if not np.any(np.maximum(normalized['edit'], normalized['influence']) *
                      (1-normalized['protect']) * normalized['composite']):
            raise PassError('EMPTY_EDIT_REGION: provide masks before RUN')
        if self.pointer() != parent_id:
            raise PassError('STALE_PARENT: inspect head; use CACHE upstream or CHECKOUT explicitly')
        token, prior = self.prior_attempt(key, nonce)
        if prior:
            return prior
        self.reserve(token)
        result = self.route('RUN', parent_id, masks, params['backend'], params,
                            processor=processor, pass_id=pass_id)
        self.bind(token, result['attempt_id'])
        return result

    def finalize_pipeline(self, parent_id, image, history, nonce):
        """Persist one final review candidate after the full Hansen-style working chain.

        Intermediate RUN stages stay in-memory and do not block downstream stages.
        Only this final candidate enters the ACCEPT/REJECT transaction.
        """
        parent, pm = self.read(parent_id, accepted=True)
        out = image_array(image)
        original_id = self.pointer('original')
        compact_history = []
        for item in history:
            compact_history.append({
                'stage': item.get('stage'),
                'status': item.get('status'),
                'result_hash': item.get('result_hash'),
                'mask_source': item.get('mask_source'),
            })
        req = {
            'parent_state_id': parent_id,
            'original_id': original_id,
            'pass_id': 'pipeline',
            'profile': 'hansen-sequential/v0.2',
            'pipeline_history': compact_history,
            'final_image_hash': array_hash(out),
            'parent_image_hash': pm['image_hash'],
        }
        key = digest(canonical(req).encode())
        token, prior = self.prior_attempt(key, nonce)
        if prior:
            return prior
        self.reserve(token)
        original, _ = self.read(original_id, accepted=True)
        qc = {
            'policy_version': 'archviz-0.2',
            'overall': 'REVIEW_REQUIRED',
            'geometry': {'status': 'NOT_EVALUATED', 'coverage': 0,
                         'reason': 'Human review required; ORIGINAL retained.'},
            'visual': {'status': 'NOT_EVALUATED', 'reason': 'Human review required.'},
            'local': {'status': 'PASS', 'protected_changed_pixels': 0,
                      'outside_alpha_changed_pixels': 0,
                      'changed_pixels': int(np.count_nonzero(
                          np.any(resize_float(parent, out.shape[1], out.shape[0]) != out, axis=2)
                      )) if parent.shape != out.shape else int(np.count_nonzero(np.any(parent != out, axis=2))),
                      'seams': 'NOT_EVALUATED', 'hallucinations': 'NOT_EVALUATED'},
            'geometry_diagnostic': geometry_diagnostic(original, out),
        }
        aid, mh = self._bundle(
            'attempt', out,
            dict(req, request_key=key, qc=qc, status_at_creation='AWAITING_ACCEPT',
                 pipeline_history=history),
        )
        with self.db:
            self.db.execute('INSERT INTO records VALUES (?,?,?,?)',
                            (aid, 'attempt', 'AWAITING_ACCEPT', mh))
        self.bind(token, aid)
        return {'status': 'AWAITING_ACCEPT', 'attempt_id': aid, 'image': out,
                'qc': qc, 'request_key': key, 'reused_attempt': False,
                'processor_calls': self.call_count()}

    def upscale_pass(self, mode, parent_id, params, processor, cache_id, nonce, protect_path=''):
        parent, pm = self.read(parent_id, accepted=True)
        h, w = parent.shape[:2]
        baseline = resize_float(parent, round(w*params['scale']), round(h*params['scale']))
        protect = load_mask(protect_path, (h, w), True)
        protect = resize_float(protect, baseline.shape[1], baseline.shape[0], True)
        original_id = self.pointer('original')
        req = dict(parent_state_id=parent_id, original_id=original_id, pass_id='upscale',
                   profile=params['backend'], parameters=params, protect_hash=array_hash(protect),
                   spatial_mapping={'type': 'resize', 'from': list(parent.shape), 'to': list(baseline.shape)},
                   composite_version='0.2', parent_image_hash=pm['image_hash'])
        key = digest(canonical(req).encode())
        if mode == 'SKIP' or params['upscale_mode'] == 'OFF':
            return {'status': 'SKIPPED', 'state_id': parent_id, 'image': parent}
        if mode == 'CACHE':
            sid = cache_id.strip() or self.auto_cache(key)
            img, m = self.read(sid, accepted=True)
            if m['parent_state_id'] != parent_id:
                raise PassError('STALE_PARENT')
            if m.get('request_key') != key:
                raise PassError('CACHE_REQUEST_MISMATCH')
            return {'status': 'CACHED', 'state_id': sid, 'image': img, 'manifest': m}
        if self.pointer() != parent_id:
            raise PassError('STALE_PARENT')
        token, prior = self.prior_attempt(key, nonce)
        if prior:
            return prior
        self.reserve(token)
        self.event('PROCESSOR_CALLED', {'request_key': key, 'profile': params['backend']})
        candidate = image_array(processor(parent, params))
        if candidate.shape != baseline.shape:
            raise PassError('INVALID_UPSCALE_DIMENSIONS')
        blend = params['detail_blend'] if params['upscale_mode'] == 'GENERATIVE' else 1.
        alpha = np.full(baseline.shape[:2], blend, np.float32)*(1-protect)
        out = baseline.copy(); active = alpha > 0
        a = alpha[active, None]
        out[active] = baseline[active]*(1-a)+candidate[active]*a
        qc = local_qc(baseline, out, {'protect': protect}, alpha)
        original, _ = self.read(original_id, accepted=True)
        qc['geometry_diagnostic'] = geometry_diagnostic(original, out)
        aid, mh = self._bundle('attempt', out, dict(req, request_key=key, qc=qc,
                               status_at_creation='AWAITING_ACCEPT'),
                               {'alpha': alpha, 'candidate': candidate, 'protect': protect})
        with self.db:
            self.db.execute('INSERT INTO records VALUES (?,?,?,?)', (aid, 'attempt', 'AWAITING_ACCEPT', mh))
        self.bind(token, aid)
        return {'status': 'AWAITING_ACCEPT', 'attempt_id': aid, 'image': out, 'qc': qc, 'request_key': key}
