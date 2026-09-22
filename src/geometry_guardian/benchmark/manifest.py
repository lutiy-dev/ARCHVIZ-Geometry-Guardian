from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime import BenchmarkCase


REQUIRED_CATEGORIES = {
    "identity",
    "appearance_change",
    "day_night",
    "repetitive_facade",
    "occlusion",
    "sparse_facade",
    "technical_transform",
    "camera_mismatch",
    "geometry_change",
}


def load_benchmark_manifest(path: str | Path) -> list[BenchmarkCase]:
    manifest_path = Path(path)
    data: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases_data = data.get("cases")
    if not isinstance(cases_data, list):
        raise ValueError("benchmark manifest must contain a 'cases' list")

    cases: list[BenchmarkCase] = []
    seen: set[str] = set()
    base = manifest_path.parent

    for raw in cases_data:
        case_id = str(raw["case_id"])
        if case_id in seen:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen.add(case_id)

        ref = Path(raw["reference_path"])
        aft = Path(raw["after_path"])
        if not ref.is_absolute():
            ref = base / ref
        if not aft.is_absolute():
            aft = base / aft

        cases.append(
            BenchmarkCase(
                case_id=case_id,
                category=str(raw["category"]),
                reference_path=str(ref),
                after_path=str(aft),
                expected_geometry_change=raw.get("expected_geometry_change"),
                notes=str(raw.get("notes", "")),
            )
        )

    return cases


def missing_required_categories(cases: list[BenchmarkCase]) -> set[str]:
    present = {case.category for case in cases}
    return REQUIRED_CATEGORIES - present
