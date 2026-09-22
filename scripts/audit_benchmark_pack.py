from __future__ import annotations

import argparse
from pathlib import Path

from geometry_guardian.benchmark.audit import (
    audit_benchmark_pack,
    write_audit_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the final pre-benchmark audit for a Geometry Guardian pack."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--variants", type=Path, required=True)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--allow-unfrozen", action="store_true")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    audit = audit_benchmark_pack(
        args.manifest,
        variant_registry_path=args.variants,
        lock_path=args.lock,
        require_frozen=not args.allow_unfrozen,
    )

    status = "READY" if audit.ready_to_run else "NOT READY"
    print(f"{status} | frozen={audit.frozen} | errors={len(audit.errors)} | warnings={len(audit.warnings)}")

    for issue in audit.issues:
        prefix = f"[{issue.severity.upper()}] {issue.code}"
        if issue.case_id:
            prefix += f" ({issue.case_id})"
        print(f"{prefix}: {issue.message}")

    if args.json_output:
        write_audit_report(audit, args.json_output)
        print(f"Audit JSON: {args.json_output}")

    return 0 if audit.ready_to_run else 2


if __name__ == "__main__":
    raise SystemExit(main())
