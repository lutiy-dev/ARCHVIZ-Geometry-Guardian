from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

from .dataset import verify_dataset_lock
from .manifest import load_benchmark_manifest
from .readiness import assess_benchmark_readiness
from .variants import (
    load_variant_registry,
    registry_case_ids,
    validate_variant_registry,
)


@dataclass(slots=True)
class PackAuditIssue:
    severity: str
    code: str
    message: str
    case_id: str | None = None


@dataclass(slots=True)
class BenchmarkPackAudit:
    ready_to_run: bool
    frozen: bool
    manifest_path: str
    variant_registry_path: str | None
    lock_path: str | None
    issues: list[PackAuditIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[PackAuditIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[PackAuditIssue]:
        return [i for i in self.issues if i.severity == "warning"]


def audit_benchmark_pack(
    manifest_path: str | Path,
    *,
    variant_registry_path: str | Path | None = None,
    lock_path: str | Path | None = None,
    require_frozen: bool = True,
) -> BenchmarkPackAudit:
    manifest = Path(manifest_path)
    issues: list[PackAuditIssue] = []

    readiness = assess_benchmark_readiness(manifest)
    for item in readiness.issues:
        issues.append(
            PackAuditIssue(
                severity=item.severity,
                code=f"readiness:{item.code}",
                message=item.message,
                case_id=item.case_id,
            )
        )

    cases = load_benchmark_manifest(manifest)
    manifest_ids = {case.case_id for case in cases}

    registry_path = None if variant_registry_path is None else Path(variant_registry_path)
    if registry_path is None:
        issues.append(
            PackAuditIssue(
                "error",
                "variant_registry_missing",
                "controlled variant registry is required before a benchmark run",
            )
        )
    elif not registry_path.exists():
        issues.append(
            PackAuditIssue(
                "error",
                "variant_registry_missing",
                f"variant registry does not exist: {registry_path}",
            )
        )
    else:
        try:
            variants = load_variant_registry(registry_path)
            variant_ids = registry_case_ids(variants)

            missing_specs = manifest_ids - variant_ids
            extra_specs = variant_ids - manifest_ids

            for case_id in sorted(missing_specs):
                issues.append(
                    PackAuditIssue(
                        "error",
                        "variant_spec_missing",
                        "manifest case has no controlled variant spec",
                        case_id,
                    )
                )
            for case_id in sorted(extra_specs):
                issues.append(
                    PackAuditIssue(
                        "warning",
                        "variant_spec_orphan",
                        "variant registry contains a case not present in manifest",
                        case_id,
                    )
                )

            validation = validate_variant_registry(variants)
            for variant in variants:
                result = validation[variant.variant_id]
                for message in result.errors:
                    issues.append(
                        PackAuditIssue(
                            "error",
                            "variant_semantics",
                            message,
                            variant.variant_id,
                        )
                    )
                for message in result.warnings:
                    issues.append(
                        PackAuditIssue(
                            "warning",
                            "variant_semantics",
                            message,
                            variant.variant_id,
                        )
                    )
        except Exception as exc:
            issues.append(
                PackAuditIssue(
                    "error",
                    "variant_registry_invalid",
                    f"failed to load/validate variant registry: {exc}",
                )
            )

    lock = None if lock_path is None else Path(lock_path)
    frozen = False
    if lock is None:
        severity = "error" if require_frozen else "warning"
        issues.append(
            PackAuditIssue(
                severity,
                "dataset_not_frozen",
                "benchmark dataset lock was not provided",
            )
        )
    elif not lock.exists():
        issues.append(
            PackAuditIssue(
                "error",
                "dataset_lock_missing",
                f"dataset lock does not exist: {lock}",
            )
        )
    else:
        try:
            lock_errors = verify_dataset_lock(manifest, lock)
            if lock_errors:
                for message in lock_errors:
                    issues.append(
                        PackAuditIssue(
                            "error",
                            "dataset_lock_mismatch",
                            message,
                        )
                    )
            else:
                frozen = True
        except Exception as exc:
            issues.append(
                PackAuditIssue(
                    "error",
                    "dataset_lock_invalid",
                    f"failed to verify dataset lock: {exc}",
                )
            )

    ready = not any(issue.severity == "error" for issue in issues)

    return BenchmarkPackAudit(
        ready_to_run=ready,
        frozen=frozen,
        manifest_path=str(manifest),
        variant_registry_path=None if registry_path is None else str(registry_path),
        lock_path=None if lock is None else str(lock),
        issues=issues,
    )


def audit_to_dict(audit: BenchmarkPackAudit) -> dict:
    return {
        "ready_to_run": audit.ready_to_run,
        "frozen": audit.frozen,
        "manifest_path": audit.manifest_path,
        "variant_registry_path": audit.variant_registry_path,
        "lock_path": audit.lock_path,
        "error_count": len(audit.errors),
        "warning_count": len(audit.warnings),
        "issues": [
            {
                "severity": issue.severity,
                "code": issue.code,
                "case_id": issue.case_id,
                "message": issue.message,
            }
            for issue in audit.issues
        ],
    }


def write_audit_report(audit: BenchmarkPackAudit, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(audit_to_dict(audit), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
