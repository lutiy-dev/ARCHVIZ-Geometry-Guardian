import json

import cv2
import numpy as np

from geometry_guardian.benchmark import assess_benchmark_readiness


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
        polygon = [[x, 10], [x + 6, 10], [x + 6, 30], [x, 30]]
        ref.append({"region_id": f"W{i:03d}", "polygon_xy": polygon})
        aft.append({"region_id": f"W{i:03d}", "polygon_xy": polygon})
    path.write_text(
        json.dumps({"reference_regions": ref, "after_regions": aft}),
        encoding="utf-8",
    )


def _build_manifest(tmp_path, *, include_gt=True):
    cases = []
    for category in CATEGORIES:
        for split in ("dev", "eval"):
            ref = tmp_path / f"{category}_{split}_ref.png"
            aft = tmp_path / f"{category}_{split}_aft.png"
            _write_image(ref)
            _write_image(aft)

            expected = None
            if category == "geometry_change":
                expected = True
            elif category != "camera_mismatch":
                expected = False

            case = {
                "case_id": f"{category}_{split}::{split}",
                "category": category,
                "reference_path": ref.name,
                "after_path": aft.name,
                "expected_geometry_change": expected,
            }
            if category == "repetitive_facade" and include_gt:
                gt = tmp_path / f"gt_{split}.json"
                _write_gt(gt)
                case["region_gt_path"] = gt.name

            cases.append(case)

    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cases": cases}), encoding="utf-8")
    return manifest


def test_complete_pack_is_ready(tmp_path):
    manifest = _build_manifest(tmp_path)
    report = assess_benchmark_readiness(manifest)
    assert report.ready is True
    assert report.errors == []


def test_missing_repetitive_gt_blocks_readiness(tmp_path):
    manifest = _build_manifest(tmp_path, include_gt=False)
    report = assess_benchmark_readiness(manifest)
    assert report.ready is False
    assert any(i.code == "missing_repetitive_gt" for i in report.errors)


def test_wrong_geometry_semantics_blocks_readiness(tmp_path):
    manifest = _build_manifest(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    target = next(c for c in data["cases"] if c["category"] == "geometry_change")
    target["expected_geometry_change"] = False
    manifest.write_text(json.dumps(data), encoding="utf-8")

    report = assess_benchmark_readiness(manifest)
    assert report.ready is False
    assert any(i.code == "geometry_change_semantics" for i in report.errors)
