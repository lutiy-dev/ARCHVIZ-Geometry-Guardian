from __future__ import annotations

import argparse
from pathlib import Path

from geometry_guardian.benchmark import (
    load_variant_registry,
    validate_variant_registry,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate controlled benchmark variant semantics."
    )
    parser.add_argument("registry", type=Path)
    args = parser.parse_args()

    variants = load_variant_registry(args.registry)
    results = validate_variant_registry(variants)

    error_count = 0
    warning_count = 0

    for variant in variants:
        result = results[variant.variant_id]
        print(
            f"[{variant.variant_id}] category={variant.category} "
            f"geometry={variant.geometry_expectation.value} valid={result.valid}"
        )
        for error in result.errors:
            print(f"  ERROR: {error}")
            error_count += 1
        for warning in result.warnings:
            print(f"  WARN:  {warning}")
            warning_count += 1

    print(
        f"variants={len(variants)} errors={error_count} warnings={warning_count}"
    )
    return 0 if error_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
