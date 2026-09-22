import json

import cv2
import numpy as np

from geometry_guardian.benchmark import (
    create_dataset_lock,
    write_dataset_lock,
)
from geometry_guardian.benchmark.audit import audit_benchmark_pack


CATEGORIES = [
    "identity",
    "appearance_change",
    "day_night",
    "repetitive_facade",
    "occlusion",
    "sparse_facade",
    "technical_transform",
    "camera_mismatch",
    "geometry_change",
]


def _write_image(path):
    image = np.zeros((80, 100, 3), dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def _write_gt(path):
    ref = []
    aft = []
    for i in range(10):
        x = 2 + i * 9
        poly = [[x, 10], [x + 6, 10], [x + 6, 30], [x, 30]]
        ref.append({"region_id": f"W{i:03d}", "polygon_xy": poly})
        aft.append({"region_id": f"W{i:03d}", "polygon_xy": poly})
    path.write_text(json.dumps({"reference_regions": ref, "after_regions": aft}), encoding="utf-8")


def _pack(tmp_path):
    cases = []
    variants = []

    for category in CATEGORIES:
        for split in ("dev", "eval"):
            ref = tmp_path / f"{category}_{split}_ref.png"
            aft = tmp_path / f"{category}_{split}_aft.png"
            _write_image(ref)
            _write_image(aft)

            case_id = f"{category}_{split}::{split}"
            expected = True if category == "geometry_change" else None if category == "camera_mismatch" else False
            case = {
                "case_id": case_id,
                "category": category,
                "reference_path": ref.name,
                "after_path": aft.name,
                "expected_geometry_change": expected,
            }
            if category == "repetitive_facade":
                gt = tmp_path / f"gt_{split}.json"
                _write_gt(gt)
                case["region_gt_path"] = gt.name
            cases.append(case)

            if category == "geometry_change":
                expectation = "changed"
                changed = ["geometry"]
                invariants = ["camera_pose", "projection"]
                known = ["W001"]
            elif category == "camera_mismatch":
                expectation = "unknown"
                changed = ["camera"]
                invariants = ["building_model_version"]
                known = []
            elif category == "identity":
                expectation = "preserved"
                changed = ["none"]
                invariants = ["camera_pose","projection","building_silhouette","facade_grid","major_openings"]
                known = []
            else:
                expectation = "preserved"
                changed = ["appearance"]
                invariants = ["camera_pose","projection","building_silhouette","facade_grid","major_openings"]
                known = []

            variants.append({
                "variant_id": case_id,
                "category": category,
                "reference_image": ref.name,
                "after_image": aft.name,
                "geometry_expectation": expectation,
                "changed_properties": changed,
                "invariant_properties": invariants,
                "controlled_change_description": "controlled test",
                "known_changed_element_ids": known,
            })

    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    registry = tmp_path / "variants.json"
    registry.write_text(json.dumps({"variants": variants}), encoding="utf-8")

    lock = create_dataset_lock(manifest, dataset_id="TEST", version="0.1")
    lock_path = tmp_path / "lock.json"
    write_dataset_lock(lock, lock_path)
    return manifest, registry, lock_path


def test_complete_pack_is_ready(tmp_path):
    manifest, registry, lock_path = _pack(tmp_path)
    audit = audit_benchmark_pack(
        manifest,
        variant_registry_path=registry,
        lock_path=lock_path,
    )
    assert audit.ready_to_run is True
    assert audit.frozen is True
    assert audit.errors == []


def test_missing_variant_spec_blocks_run(tmp_path):
    manifest, registry, lock_path = _pack(tmp_path)
    data = json.loads(registry.read_text(encoding="utf-8"))
    data["variants"] = data["variants"][:-1]
    registry.write_text(json.dumps(data), encoding="utf-8")

    audit = audit_benchmark_pack(
        manifest,
        variant_registry_path=registry,
        lock_path=lock_path,
    )
    assert audit.ready_to_run is False
    assert any(i.code == "variant_spec_missing" for i in audit.errors)


def test_mutated_dataset_blocks_run(tmp_path):
    manifest, registry, lock_path = _pack(tmp_path)
    first_image = next(tmp_path.glob("*_ref.png"))
    first_image.write_bytes(b"changed-after-freeze")

    audit = audit_benchmark_pack(
        manifest,
        variant_registry_path=registry,
        lock_path=lock_path,
    )
    assert audit.ready_to_run is False
    assert any(i.code == "dataset_lock_mismatch" for i in audit.errors)
