from __future__ import annotations

import argparse
from pathlib import Path

from geometry_guardian.benchmark import (
    load_region_box_csv,
    rows_to_ground_truth,
    validate_ground_truth_against_images,
    write_ground_truth_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build validated semantic region GT JSON from a CSV table."
    )
    parser.add_argument("csv", type=Path)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-common-ids", type=int, default=10)
    args = parser.parse_args()

    rows = load_region_box_csv(args.csv)
    gt = rows_to_ground_truth(rows)
    errors = validate_ground_truth_against_images(
        gt,
        reference_image_path=args.reference,
        after_image_path=args.after,
        minimum_common_ids=args.minimum_common_ids,
    )

    if errors:
        print("GT validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 2

    write_ground_truth_json(
        gt,
        args.output,
        source_csv=str(args.csv),
    )
    print(
        f"Wrote {args.output}: "
        f"reference={len(gt.reference_regions)} "
        f"after={len(gt.after_regions)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
