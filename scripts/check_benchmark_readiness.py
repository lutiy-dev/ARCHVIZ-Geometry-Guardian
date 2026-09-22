from __future__ import annotations

import argparse
from pathlib import Path

from geometry_guardian.benchmark import assess_benchmark_readiness


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check whether a Geometry Guardian benchmark pack is ready."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--minimum-repetitive-region-ids", type=int, default=10)
    args = parser.parse_args()

    report = assess_benchmark_readiness(
        args.manifest,
        minimum_repetitive_region_ids=args.minimum_repetitive_region_ids,
    )

    print(
        f"cases={report.case_count} categories={report.category_count} "
        f"ready={report.ready}"
    )

    if not report.issues:
        print("READY: no readiness issues found")
        return 0

    for issue in report.issues:
        prefix = f"[{issue.severity.upper()}] {issue.code}"
        if issue.case_id:
            prefix += f" ({issue.case_id})"
        print(f"{prefix}: {issue.message}")

    return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
