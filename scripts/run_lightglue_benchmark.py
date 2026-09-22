from __future__ import annotations

import argparse
from pathlib import Path

from geometry_guardian.benchmark import (
    load_benchmark_manifest,
    missing_required_categories,
    run_benchmark_case,
    write_json_report,
)
from geometry_guardian.features.providers.lightglue_provider import (
    LightGlueProvider,
    LightGlueProviderConfig,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run ARCHVIZ Geometry Guardian LightGlue benchmark manifest."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("benchmark_results.json"))
    parser.add_argument("--extractor", default="aliked")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--max-keypoints", type=int, default=2048)
    parser.add_argument("--filter-threshold", type=float, default=0.1)
    parser.add_argument("--allow-superpoint-license", action="store_true")
    args = parser.parse_args()

    cases = load_benchmark_manifest(args.manifest)
    missing = missing_required_categories(cases)
    if missing:
        print(
            "WARNING: manifest does not yet cover required categories: "
            + ", ".join(sorted(missing))
        )

    provider = LightGlueProvider(
        LightGlueProviderConfig(
            extractor=args.extractor,
            max_num_keypoints=args.max_keypoints,
            filter_threshold=args.filter_threshold,
            device=args.device,
            allow_restricted_superpoint_license=args.allow_superpoint_license,
        )
    )

    results = []
    for case in cases:
        print(f"[{case.case_id}] {case.category}")
        result = run_benchmark_case(provider, case)
        results.append(result)
        metrics = result.metrics
        registration = metrics.registration.registration
        print(
            f"  matches={metrics.match_count} "
            f"coverage={metrics.correspondence_quality.spatial_coverage_fraction:.3f} "
            f"registration={registration.status.value} "
            f"time={result.elapsed_ms:.1f}ms "
            f"vram={result.peak_vram_mb if result.peak_vram_mb is not None else 'n/a'}"
        )

    write_json_report(results, args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
