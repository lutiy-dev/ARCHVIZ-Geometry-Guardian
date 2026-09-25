"""Immutable image state store and transactional manual decisions."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid

import numpy as np
from PIL import Image


class PassError(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def image_array(value):
    a = np.asarray(value, dtype=np.float32)
    if a.ndim != 3 or a.shape[2] != 3 or min(a.shape[:2]) < 1:
        raise PassError("INVALID_IMAGE: expected H,W,3 RGB")
    if not np.isfinite(a).all() or a.min() < 0 or a.max() > 1:
        raise PassError("INVALID_IMAGE: expected finite values in [0,1]")
    return np.ascontiguousarray(a)


def array_hash(a):
    return digest(canonical({"shape": list(a.shape), "dtype": a.dtype.str}).encode() + a.tobytes())


def mask_array(value, shape, binary=False):
    a = np.asarray(value, dtype=np.float32)
    if a.shape != shape or not np.isfinite(a).all() or a.min() < 0 or a.max() > 1:
        raise PassError("INVALID_MASK: dimensions/range")
    if binary and not np.isin(a, (0, 1)).all():
        raise PassError("INVALID_MASK: edit/influence/protect must be binary; feather composite only")
    return np.ascontiguousarray(a)


def composite(parent, candidate, masks):
    p, c = image_array(parent), image_array(candidate)
    if p.shape != c.shape:
        raise PassError("INVALID_SPATIAL_MAPPING: full-frame prototype requires identical dimensions")
    m = {k: mask_array(masks[k], p.shape[:2], k != "composite")
         for k in ("edit", "influence", "protect", "composite")}
    allowed = np.maximum(m["edit"], m["influence"])
    alpha = m["composite"] * allowed * (1 - m["protect"])
    out = p.copy()
    active = alpha > 0
    a = alpha[active, None]
    out[active] = p[active] * (1 - a) + c[active] * a
    out[~active] = p[~active]
    return out, alpha


def local_qc(parent, result, masks, alpha):
    unchanged = np.all(parent == result, axis=2)
    protected = masks["protect"] == 1
    outside = alpha == 0
    count_protected = int(np.count_nonzero(~unchanged & protected))
    count_outside = int(np.count_nonzero(~unchanged & outside))
    return {
        "policy_version": "archviz-0.2", "overall": "REVIEW_REQUIRED",
        "geometry": {"status": "NOT_EVALUATED", "coverage": 0,
                     "reason": "Geometry detector not implemented; ORIGINAL is retained."},
        "visual": {"status": "NOT_EVALUATED", "reason": "Human review required."},
        "local": {"status": "PASS" if not count_protected and not count_outside else "FAIL",
                  "protected_changed_pixels": count_protected,
                  "outside_alpha_changed_pixels": count_outside,
                  "changed_pixels": int(np.count_nonzero(~unchanged)),
                  "seams": "NOT_EVALUATED", "hallucinations": "NOT_EVALUATED"},
    }


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "state.sqlite3", timeout=15)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, kind TEXT NOT NULL,
            status TEXT NOT NULL, manifest_hash TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS pointers(name TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS decisions(attempt TEXT PRIMARY KEY, action TEXT NOT NULL,
            result TEXT NOT NULL, note TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS events(n INTEGER PRIMARY KEY, event TEXT NOT NULL, data TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    def event(self, name, data):
        with self.db:
            self.db.execute("INSERT INTO events(event,data) VALUES (?,?)", (name, canonical(data)))

    def call_count(self):
        return self.db.execute("SELECT count(*) FROM events WHERE event='PROCESSOR_CALLED'").fetchone()[0]

    def pointer(self, name="head"):
        row = self.db.execute("SELECT value FROM pointers WHERE name=?", (name,)).fetchone()
        return row[0] if row else None

    @staticmethod
    def valid_id(value):
        if not isinstance(value, str) or not re.fullmatch(r"[sa]_[0-9a-f]{32}", value):
            raise PassError("INVALID_STATE_ID")
        return value

    def _bundle(self, kind, image, metadata, extras=None):
        sid = ("s_" if kind == "state" else "a_") + uuid.uuid4().hex
        folder = self.root / sid
        folder.mkdir()
        a = image_array(image)
        arrays = {"image": a, **(extras or {})}
        hashes = {}
        for name, value in arrays.items():
            v = np.ascontiguousarray(value)
            with (folder / (name + ".npy")).open("xb") as f:
                np.save(f, v, allow_pickle=False)
                f.flush(); os.fsync(f.fileno())
            hashes[name] = array_hash(v)
        Image.fromarray(np.rint(a * 255).astype(np.uint8)).save(folder / "preview.png")
        metadata = dict(metadata, state_id=sid if kind == "state" else None,
                        attempt_id=sid if kind == "attempt" else metadata.get("attempt_id"),
                        artifact_id=sid, kind=kind, image_hash=hashes["image"],
                        arrays=hashes, dimensions=list(a.shape), schema_version="0.1")
        qc = canonical(metadata["qc"]).encode("utf-8")
        metadata["qc_report_hash"] = digest(qc)
        with (folder / "qc_report.json").open("xb") as f:
            f.write(qc); f.flush(); os.fsync(f.fileno())
        raw = canonical(metadata).encode("utf-8")
        with (folder / "manifest.json").open("xb") as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        return sid, digest(raw)

    def read(self, sid, accepted=False):
        self.valid_id(sid)
        row = self.db.execute("SELECT kind,status,manifest_hash FROM records WHERE id=?", (sid,)).fetchone()
        if not row:
            raise PassError("INVALID_CACHE: unknown state/attempt")
        if accepted and (row[0] != "state" or row[1] != "ACCEPTED"):
            raise PassError("UNACCEPTED_INPUT")
        folder = self.root / sid
        try:
            raw = (folder / "manifest.json").read_bytes()
            if digest(raw) != row[2]:
                raise ValueError("manifest hash mismatch")
            m = json.loads(raw)
            if digest((folder / "qc_report.json").read_bytes()) != m["qc_report_hash"]:
                raise ValueError("QC hash mismatch")
            for name, expected in m["arrays"].items():
                a = np.load(folder / (name + ".npy"), allow_pickle=False)
                if array_hash(a) != expected:
                    raise ValueError("array hash mismatch: " + name)
            image = np.load(folder / "image.npy", allow_pickle=False)
        except (OSError, ValueError, KeyError) as e:
            raise PassError("INVALID_CACHE: " + str(e)) from e
        return image, dict(m, current_status=row[1])

    def initialize(self, original):
        a = image_array(original)
        existing = self.pointer("original")
        if existing:
            _, m = self.read(existing, accepted=True)
            if m["image_hash"] != array_hash(a):
                raise PassError("ORIGINAL_IMMUTABLE: use a new project")
            return existing
        sid, mh = self._bundle("state", a, {"parent_state_id": None, "original_id": None,
            "pass_id": "original", "qc": {"geometry": {"status": "NOT_EVALUATED"}},
            "status_at_creation": "ACCEPTED"})
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.pointer("original"):
                raise PassError("INITIALIZATION_CONFLICT")
            self.db.execute("INSERT INTO records VALUES (?,?,?,?)", (sid, "state", "ACCEPTED", mh))
            self.db.executemany("INSERT INTO pointers VALUES (?,?)", [("head", sid), ("original", sid)])
            self.db.commit()
        except Exception:
            self.db.rollback(); raise
        return sid

    def checkout(self, sid):
        self.read(sid, accepted=True)
        with self.db:
            self.db.execute("UPDATE pointers SET value=? WHERE name='head'", (sid,))
            self.db.execute("INSERT INTO events(event,data) VALUES ('CHECKOUT',?)", (canonical({"state_id": sid}),))

    def request(self, parent_id, masks, profile, parameters, pass_id="facade"):
        parent, _ = self.read(parent_id, accepted=True)
        normalized = {k: mask_array(masks[k], parent.shape[:2], k != "composite")
                      for k in ("edit", "protect", "influence", "composite")}
        original = self.pointer("original")
        _, original_meta = self.read(original, accepted=True)
        data = {"parent_state_id": parent_id, "original_id": original,
                "original_hash": original_meta["image_hash"], "pass_id": pass_id,
                "profile": profile, "parameters": parameters,
                "masks": {k: array_hash(v) for k, v in normalized.items()},
                "spatial_mapping": {"type": "identity", "dimensions": list(parent.shape)},
                "composite_version": "0.1", "passport_version": "image-only-0.1"}
        return parent, normalized, data, digest(canonical(data).encode())

    def route(self, mode, parent_id, masks, profile, parameters, processor=None,
              cache_id="", enabled=True, pass_id="facade"):
        parent, masks, req, key = self.request(parent_id, masks, profile, parameters, pass_id)
        effective = mode if enabled else "SKIP"
        if effective == "SKIP":
            return {"status": "SKIPPED", "state_id": parent_id, "image": parent,
                    "request_key": key, "processor_calls": self.call_count()}
        if effective == "CACHE":
            cached, m = self.read(cache_id, accepted=True)
            if m["parent_state_id"] != parent_id:
                raise PassError("STALE_PARENT")
            if m.get("request_key") != key:
                raise PassError("CACHE_REQUEST_MISMATCH")
            return {"status": "CACHED", "state_id": cache_id, "image": cached,
                    "manifest": m, "processor_calls": self.call_count()}
        if effective != "RUN":
            raise PassError("INVALID_MODE")
        if self.pointer() != parent_id:
            raise PassError("STALE_PARENT: checkout intended parent first")
        if processor is None:
            raise PassError("MISSING_PROCESSOR")
        self.event("PROCESSOR_CALLED", {"request_key": key, "profile": profile})
        try:
            raw = image_array(processor(parent.copy(), dict(parameters)))
            out, alpha = composite(parent, raw, masks)
            qc = self.assess(parent, out, masks, alpha)
            aid, mh = self._bundle("attempt", out, dict(req, request_key=key, qc=qc,
                status_at_creation="AWAITING_ACCEPT", processor_metadata={"profile": profile,
                "actual_parameters": parameters, "execution_status": "SUCCESS"}),
                {"candidate": raw, "alpha": alpha, **masks})
            with self.db:
                self.db.execute("INSERT INTO records VALUES (?,?,?,?)", (aid, "attempt", "AWAITING_ACCEPT", mh))
            return {"status": "AWAITING_ACCEPT", "attempt_id": aid, "image": out,
                    "qc": qc, "request_key": key, "processor_calls": self.call_count()}
        except Exception as e:
            self.event("PROCESSOR_FAILED", {"request_key": key, "error": str(e)})
            raise

    def assess(self, parent, out, masks, alpha):
        return local_qc(parent, out, masks, alpha)

    def decide(self, attempt_id, action, note="", reviewed=False):
        if action not in ("ACCEPT", "REJECT"):
            raise PassError("INVALID_DECISION")
        self.valid_id(attempt_id)
        prior = self.db.execute("SELECT action,result FROM decisions WHERE attempt=?", (attempt_id,)).fetchone()
        if prior:
            if prior[0] != action:
                raise PassError("DECISION_ALREADY_COMMITTED")
            self.read(prior[1], accepted=True)
            return prior[1]
        image, m = self.read(attempt_id)
        if m["current_status"] != "AWAITING_ACCEPT":
            raise PassError("NOT_AWAITING_ACCEPT")
        parent = m["parent_state_id"]
        self.read(parent, accepted=True)
        if action == "ACCEPT":
            if not reviewed or not note.strip():
                raise PassError("MANUAL_REVIEW_REQUIRED: acknowledge unimplemented geometry/visual QC")
            if m["qc"]["local"]["status"] != "PASS":
                raise PassError("LOCAL_QC_FAILED")
            accepted_metadata = {k: v for k, v in m.items() if k not in
                ("current_status", "arrays", "state_id", "artifact_id", "image_hash", "kind", "qc_report_hash")}
            sid, mh = self._bundle("state", image, dict(accepted_metadata,
                status_at_creation="ACCEPTED", review={"acknowledged": True, "note": note}))
        else:
            sid, mh = parent, None
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT 1 FROM decisions WHERE attempt=?", (attempt_id,)).fetchone():
                raise PassError("DECISION_CONFLICT")
            if action == "ACCEPT":
                if self.pointer() != parent:
                    raise PassError("STALE_PARENT")
                self.db.execute("INSERT INTO records VALUES (?,?,?,?)", (sid, "state", "ACCEPTED", mh))
                self.db.execute("UPDATE pointers SET value=? WHERE name='head'", (sid,))
            self.db.execute("UPDATE records SET status=? WHERE id=?",
                            ("ACCEPTED" if action == "ACCEPT" else "REJECTED", attempt_id))
            self.db.execute("INSERT INTO decisions VALUES (?,?,?,?)", (attempt_id, action, sid, note))
            self.db.commit()
        except Exception:
            self.db.rollback(); raise
        return sid


def fixture_image(size=64):
    y, x = np.mgrid[:size, :size]
    return np.stack([x / max(size - 1, 1), y / max(size - 1, 1), np.full_like(x, .35, dtype=float)], -1).astype(np.float32)


def fixture_masks(shape):
    h, w = shape
    edit = np.zeros(shape, np.float32); edit[h//4:3*h//4, w//4:3*w//4] = 1
    influence = np.zeros(shape, np.float32); influence[3*h//4:min(h, 3*h//4+3), w//4:3*w//4] = 1
    protect = np.zeros(shape, np.float32); protect[:, w//2:w//2+2] = 1
    return {"edit": edit, "influence": influence, "protect": protect,
            "composite": np.full(shape, .5, np.float32)}


def test_processor(parent, parameters):
    return np.full_like(parent, float(parameters.get("level", .85)))
