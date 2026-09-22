from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import cv2

from .manifest import REQUIRED_CATEGORIES, load_benchmark_manifest
from .regions import load_pair_region_ground_truth
from .splits import split_cases_by_tag, validate_frozen_split


@dataclass(slots=True)
class ReadinessIssue:
    severity: str
    code: str
    message: str
    case_id: str | None = None


@dataclass(slots=True)
class BenchmarkReadinessReport:
    ready: bool
    manifest_path: str
    case_count: int
    category_count: int
    issues: list[ReadinessIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ReadinessIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ReadinessIssue]:
        return [i for i in self.issues if i.severity == "warning"]


def _resolve(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else base / path


def _image_size(path: Path) -> tuple[int, int] | None:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        return None
    h, w = image.shape[:2]
    return (w, h)


def _split_name(case_id: str) -> str | None:
    if case_id.endswith("::dev"):
        return "dev"
    if case_id.endswith("::eval"):
        return "eval"
    return None


def assess_benchmark_readiness(
    manifest_path: str | Path,
    *,
    minimum_repetitive_region_ids: int = 10,
) -> BenchmarkReadinessReport:
    manifest = Path(manifest_path)
    base = manifest.parent
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    cases_raw = raw.get("cases", [])
    cases = load_benchmark_manifest(manifest)

    issues: list[ReadinessIssue] = []

    present_categories = {case.category for case in cases}
    missing_categories = REQUIRED_CATEGORIES - present_categories
    for category in sorted(missing_categories):
        issues.append(
            ReadinessIssue(
                "error",
                "missing_category",
                f"required category is absent: {category}",
            )
        )

    split = split_cases_by_tag(cases)
    for message in validate_frozen_split(split):
        issues.append(ReadinessIssue("error", "split_invalid", message))

    raw_by_id = {str(item["case_id"]): item for item in cases_raw}

    # Detect accidental data leakage: exact image path reused across dev/eval.
    path_splits: dict[str, set[str]] = {}

    for case in cases:
        raw_case = raw_by_id[case.case_id]
        split_name = _split_name(case.case_id)
        if split_name is None:
            issues.append(
                ReadinessIssue(
                    "error",
                    "missing_split_suffix",
                    "case_id must end with ::dev or ::eval",
                    case.case_id,
                )
            )

        ref_path = _resolve(base, raw_case.get("reference_path"))
        aft_path = _resolve(base, raw_case.get("after_path"))

        for role, path in (("reference", ref_path), ("after", aft_path)):
            if path is None or not path.exists():
                issues.append(
                    ReadinessIssue(
                        "error",
                        "missing_image",
                        f"{role} image is missing: {path}",
                        case.case_id,
                    )
                )
                continue
            if split_name is not None:
                path_splits.setdefault(str(path.resolve()), set()).add(split_name)

        if ref_path and aft_path and ref_path.exists() and aft_path.exists():
            ref_size = _image_size(ref_path)
            aft_size = _image_size(aft_path)
            if ref_size is None:
                issues.append(
                    ReadinessIssue(
                        "error",
                        "unreadable_image",
                        f"cannot decode reference image: {ref_path}",
                        case.case_id,
                    )
                )
            if aft_size is None:
                issues.append(
                    ReadinessIssue(
                        "error",
                        "unreadable_image",
                        f"cannot decode AFTER image: {aft_path}",
                        case.case_id,
                    )
                )
            if ref_size and aft_size:
                rw, rh = ref_size
                aw, ah = aft_size
                ref_aspect = rw / rh
                aft_aspect = aw / ah
                aspect_delta = abs(aft_aspect / ref_aspect - 1.0)
                if aspect_delta > 0.01 and case.category != "technical_transform":
                    issues.append(
                        ReadinessIssue(
                            "warning",
                            "aspect_ratio_mismatch",
                            f"aspect ratio differs by {aspect_delta * 100:.2f}%",
                            case.case_id,
                        )
                    )

        expected = raw_case.get("expected_geometry_change")
        if case.category == "geometry_change" and expected is not True:
            issues.append(
                ReadinessIssue(
                    "error",
                    "geometry_change_semantics",
                    "geometry_change case must set expected_geometry_change=true",
                    case.case_id,
                )
            )
        if case.category in {
            "identity",
            "appearance_change",
            "day_night",
            "repetitive_facade",
            "occlusion",
            "sparse_facade",
            "technical_transform",
        } and expected is not False:
            issues.append(
                ReadinessIssue(
                    "error",
                    "preservation_semantics",
                    f"{case.category} case must set expected_geometry_change=false",
                    case.case_id,
                )
            )

        if case.category == "repetitive_facade":
            gt_path = _resolve(base, raw_case.get("region_gt_path"))
            if gt_path is None:
                issues.append(
                    ReadinessIssue(
                        "error",
                        "missing_repetitive_gt",
                        "repetitive_facade case requires region_gt_path",
                        case.case_id,
                    )
                )
            elif not gt_path.exists():
                issues.append(
                    ReadinessIssue(
                        "error",
                        "missing_repetitive_gt",
                        f"region GT file is missing: {gt_path}",
                        case.case_id,
                    )
                )
            else:
                try:
                    gt = load_pair_region_ground_truth(gt_path)
                    ref_ids = {r.region_id for r in gt.reference_regions}
                    aft_ids = {r.region_id for r in gt.after_regions}
                    common = ref_ids & aft_ids
                    if len(common) < minimum_repetitive_region_ids:
                        issues.append(
                            ReadinessIssue(
                                "error",
                                "insufficient_repetitive_gt",
                                f"need at least {minimum_repetitive_region_ids} common region IDs; found {len(common)}",
                                case.case_id,
                            )
                        )
                    if len(ref_ids) != len(gt.reference_regions):
                        issues.append(
                            ReadinessIssue(
                                "error",
                                "duplicate_reference_region_id",
                                "reference GT contains duplicate region IDs",
                                case.case_id,
                            )
                        )
                    if len(aft_ids) != len(gt.after_regions):
                        issues.append(
                            ReadinessIssue(
                                "error",
                                "duplicate_after_region_id",
                                "AFTER GT contains duplicate region IDs",
                                case.case_id,
                            )
                        )
                except Exception as exc:
                    issues.append(
                        ReadinessIssue(
                            "error",
                            "invalid_region_gt",
                            f"cannot load region GT: {exc}",
                            case.case_id,
                        )
                    )

    for path, splits in sorted(path_splits.items()):
        if len(splits) > 1:
            issues.append(
                ReadinessIssue(
                    "warning",
                    "cross_split_image_reuse",
                    f"same image is referenced by both dev and eval: {path}",
                )
            )

    return BenchmarkReadinessReport(
        ready=not any(i.severity == "error" for i in issues),
        manifest_path=str(manifest),
        case_count=len(cases),
        category_count=len(present_categories),
        issues=issues,
    )
