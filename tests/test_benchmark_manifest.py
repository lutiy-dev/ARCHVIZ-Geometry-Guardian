import json

from geometry_guardian.benchmark import (
    REQUIRED_CATEGORIES,
    load_benchmark_manifest,
    missing_required_categories,
)


def test_manifest_loads_relative_paths(tmp_path):
    payload = {
        "cases": [
            {
                "case_id": "identity_001",
                "category": "identity",
                "reference_path": "a.png",
                "after_path": "b.png",
                "expected_geometry_change": False,
            }
        ]
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    cases = load_benchmark_manifest(path)
    assert len(cases) == 1
    assert cases[0].reference_path == str(tmp_path / "a.png")
    assert "identity" not in missing_required_categories(cases)


def test_required_category_set_contains_archviz_failure_modes():
    for category in (
        "day_night",
        "repetitive_facade",
        "occlusion",
        "camera_mismatch",
        "geometry_change",
    ):
        assert category in REQUIRED_CATEGORIES
