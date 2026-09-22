from __future__ import annotations

import argparse
from pathlib import Path

from geometry_guardian.benchmark import initialize_benchmark_pack


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize a real-image Geometry Guardian benchmark pack."
    )
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--eval-reference", type=Path)
    parser.add_argument("--dataset-id", default="ARCHVIZ_QC_PACK_001")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    layout = initialize_benchmark_pack(
        args.output_dir,
        reference_image=args.reference,
        evaluation_reference_image=args.eval_reference,
        dataset_id=args.dataset_id,
        force=args.force,
    )

    print(f"Initialized: {layout.root}")
    print(f"Manifest:    {layout.manifest_path}")
    print(f"Plan:        {layout.plan_path}")
    print("Next: add real variants and run check_benchmark_readiness.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
