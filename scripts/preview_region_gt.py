from __future__ import annotations

import argparse
from pathlib import Path

from geometry_guardian.benchmark import (
    load_pair_region_ground_truth,
    write_gt_previews,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render labeled BEFORE/AFTER previews for region GT."
    )
    parser.add_argument("gt", type=Path)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    gt = load_pair_region_ground_truth(args.gt)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    ref_output = args.output_dir / "reference_gt_preview.png"
    aft_output = args.output_dir / "after_gt_preview.png"

    write_gt_previews(
        gt,
        reference_image_path=args.reference,
        after_image_path=args.after,
        reference_output_path=ref_output,
        after_output_path=aft_output,
    )

    print(f"Reference preview: {ref_output}")
    print(f"AFTER preview:     {aft_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
