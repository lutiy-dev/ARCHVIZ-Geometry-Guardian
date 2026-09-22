from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from .correspondence import CorrespondenceSet


class QualityStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    INSUFFICIENT = "insufficient"


@dataclass(slots=True)
class CorrespondenceQuality:
    status: QualityStatus
    match_count: int
    occupied_grid_cells: int
    total_grid_cells: int
    spatial_coverage_fraction: float
    reference_bbox_fraction: float
    after_bbox_fraction: float
    unique_reference_features: int | None
    unique_after_features: int | None
    duplicate_reference_feature_fraction: float | None
    duplicate_after_feature_fraction: float | None
    reasons: list[str]


def _grid_coverage(
    points: np.ndarray,
    image_size: tuple[int, int],
    grid_shape: tuple[int, int],
) -> tuple[int, int, float]:
    width, height = image_size
    cols, rows = grid_shape
    if len(points) == 0:
        return 0, cols * rows, 0.0

    x = np.clip(points[:, 0] / max(width, 1), 0, 0.999999)
    y = np.clip(points[:, 1] / max(height, 1), 0, 0.999999)
    cx = np.floor(x * cols).astype(int)
    cy = np.floor(y * rows).astype(int)
    occupied = len(set(zip(cx.tolist(), cy.tolist())))
    total = cols * rows
    return occupied, total, occupied / total


def _bbox_fraction(points: np.ndarray, image_size: tuple[int, int]) -> float:
    if len(points) < 2:
        return 0.0
    width, height = image_size
    span_x = float(points[:, 0].max() - points[:, 0].min())
    span_y = float(points[:, 1].max() - points[:, 1].min())
    return max(span_x, 0.0) * max(span_y, 0.0) / max(width * height, 1)


def _duplicate_fraction(ids: list[str | int | None]) -> tuple[int | None, float | None]:
    usable = [i for i in ids if i is not None]
    if not usable:
        return None, None
    unique = len(set(usable))
    duplicate_count = len(usable) - unique
    return unique, duplicate_count / len(usable)


def evaluate_correspondence_quality(
    matches: CorrespondenceSet,
    *,
    min_match_count: int = 12,
    grid_shape: tuple[int, int] = (4, 4),
    min_spatial_coverage_fraction: float = 0.25,
    min_bbox_fraction: float = 0.20,
    max_duplicate_feature_fraction: float = 0.10,
) -> CorrespondenceQuality:
    errors = matches.validate()
    if errors:
        return CorrespondenceQuality(
            QualityStatus.INSUFFICIENT,
            len(matches.correspondences),
            0,
            grid_shape[0] * grid_shape[1],
            0.0,
            0.0,
            0.0,
            None,
            None,
            None,
            None,
            [f"invalid correspondence set: {e}" for e in errors],
        )

    ref = matches.reference_points()
    aft = matches.after_points()
    count = len(ref)

    ref_occ, total_cells, ref_grid = _grid_coverage(
        ref, matches.reference_image_size, grid_shape
    )
    aft_occ, _, aft_grid = _grid_coverage(
        aft, matches.after_image_size, grid_shape
    )
    occupied = min(ref_occ, aft_occ)
    spatial = min(ref_grid, aft_grid)

    ref_bbox = _bbox_fraction(ref, matches.reference_image_size)
    aft_bbox = _bbox_fraction(aft, matches.after_image_size)

    ref_unique, ref_dup = _duplicate_fraction(
        [m.reference_feature_id for m in matches.correspondences]
    )
    aft_unique, aft_dup = _duplicate_fraction(
        [m.after_feature_id for m in matches.correspondences]
    )

    reasons: list[str] = []
    insufficient = False
    warn = False

    if count < min_match_count:
        reasons.append(f"match count {count} < {min_match_count}")
        insufficient = True

    if spatial < min_spatial_coverage_fraction:
        reasons.append(
            f"spatial grid coverage {spatial:.3f} < {min_spatial_coverage_fraction:.3f}"
        )
        insufficient = True

    if min(ref_bbox, aft_bbox) < min_bbox_fraction:
        reasons.append(
            f"point-cloud bbox coverage {min(ref_bbox, aft_bbox):.3f} < "
            f"{min_bbox_fraction:.3f}"
        )
        insufficient = True

    for side, duplicate_fraction in (
        ("reference", ref_dup),
        ("after", aft_dup),
    ):
        if (
            duplicate_fraction is not None
            and duplicate_fraction > max_duplicate_feature_fraction
        ):
            reasons.append(
                f"{side} duplicate feature fraction {duplicate_fraction:.3f} > "
                f"{max_duplicate_feature_fraction:.3f}"
            )
            warn = True

    if insufficient:
        status = QualityStatus.INSUFFICIENT
    elif warn:
        status = QualityStatus.WARN
    else:
        status = QualityStatus.PASS
        reasons.append("correspondence support is spatially distributed")

    return CorrespondenceQuality(
        status=status,
        match_count=count,
        occupied_grid_cells=occupied,
        total_grid_cells=total_cells,
        spatial_coverage_fraction=spatial,
        reference_bbox_fraction=ref_bbox,
        after_bbox_fraction=aft_bbox,
        unique_reference_features=ref_unique,
        unique_after_features=aft_unique,
        duplicate_reference_feature_fraction=ref_dup,
        duplicate_after_feature_fraction=aft_dup,
        reasons=reasons,
    )
