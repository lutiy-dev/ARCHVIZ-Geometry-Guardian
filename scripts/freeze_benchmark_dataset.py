from __future__ import annotations

import argparse
from pathlib import Path

from geometry_guardian.benchmark import (
    create_dataset_lock,
    load_benchmark_manifest,
    missing_required_categories,
    split_cases_by_tag,
    validate_frozen_split,
    write_dataset_lock,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze a Geometry Guardian benchmark dataset."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark_dataset.lock.json"),
    )
    args = parser.parse_args()

    cases = load_benchmark_manifest(args.manifest)

    missing = missing_required_categories(cases)
    if missing:
        raise SystemExit(
            "dataset is incomplete; missing categories: "
            + ", ".join(sorted(missing))
        )

    split = split_cases_by_tag(cases)
    split_errors = validate_frozen_split(split)
    if split_errors:
        raise SystemExit("split validation failed: " + "; ".join(split_errors))

    lock = create_dataset_lock(
        args.manifest,
        dataset_id=args.dataset_id,
        version=args.version,
    )
    write_dataset_lock(lock, args.output)

    print(
        f"Frozen {args.dataset_id} {args.version}: "
        f"{len(lock.files)} files -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
