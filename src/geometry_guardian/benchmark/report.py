from __future__ import annotations

import json
from pathlib import Path

from .runtime import RuntimeBenchmarkResult


def write_json_report(
    results: list[RuntimeBenchmarkResult],
    path: str | Path,
) -> None:
    payload = {
        "schema_version": "0.1",
        "case_count": len(results),
        "results": [result.to_dict() for result in results],
    }
    Path(path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
