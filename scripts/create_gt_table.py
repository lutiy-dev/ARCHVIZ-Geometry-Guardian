from __future__ import annotations

import argparse
from pathlib import Path

from geometry_guardian.benchmark import write_region_box_csv_template


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a spreadsheet-friendly region GT table."
    )
    parser.add_argument("output", type=Path)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--prefix", default="W")
    parser.add_argument("--start", type=int, default=1)
    args = parser.parse_args()

    if args.count <= 0:
        raise SystemExit("--count must be positive")

    write_region_box_csv_template(
        args.output,
        region_count=args.count,
        id_prefix=args.prefix,
        start_index=args.start,
    )
    print(f"Wrote GT table template: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
