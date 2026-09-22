from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Iterable

from geometry_guardian.qc.statuses import QCStatus


BBox = tuple[float, float, float, float]


@dataclass(slots=True)
class CandidateOpening:
    candidate_id: str
    facade_id: str
    bbox_xyxy: BBox
    visibility: float = 1.0


@dataclass(slots=True)
class OpeningMatch:
    reference_id: str
    candidate_id: str | None
    status: QCStatus
    cost: float | None
    ambiguity_margin: float | None
    reasons: list[str]


def _center(box: BBox) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return ((x1 + x2) * 0.5, (y1 + y2) * 0.5)


def _size(box: BBox) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return (max(x2 - x1, 1e-6), max(y2 - y1, 1e-6))


def pair_cost(reference: BBox, candidate: BBox) -> float:
    rc = _center(reference)
    cc = _center(candidate)
    rw, rh = _size(reference)
    cw, ch = _size(candidate)

    diag = hypot(rw, rh)
    center_term = hypot(cc[0] - rc[0], cc[1] - rc[1]) / max(diag, 1e-6)
    size_term = 0.5 * (abs(cw - rw) / rw + abs(ch - rh) / rh)
    return 0.7 * center_term + 0.3 * size_term


def match_reference_opening(
    *,
    reference_id: str,
    facade_id: str,
    expected_bbox: BBox,
    candidates: Iterable[CandidateOpening],
    search_radius_px: float,
    max_scale_ratio: float = 2.0,
    accept_cost: float = 0.35,
    ambiguity_margin: float = 0.05,
    min_visibility: float = 0.35,
) -> OpeningMatch:
    rc = _center(expected_bbox)
    rw, rh = _size(expected_bbox)

    eligible: list[tuple[float, CandidateOpening]] = []
    low_visibility = False

    for candidate in candidates:
        if candidate.facade_id != facade_id:
            continue

        cc = _center(candidate.bbox_xyxy)
        if hypot(cc[0] - rc[0], cc[1] - rc[1]) > search_radius_px:
            continue

        cw, ch = _size(candidate.bbox_xyxy)
        scale = max(cw / rw, rw / cw, ch / rh, rh / ch)
        if scale > max_scale_ratio:
            continue

        if candidate.visibility < min_visibility:
            low_visibility = True
            continue

        eligible.append((pair_cost(expected_bbox, candidate.bbox_xyxy), candidate))

    if not eligible:
        if low_visibility:
            return OpeningMatch(
                reference_id,
                None,
                QCStatus.INSUFFICIENT_DATA,
                None,
                None,
                ["candidate region exists but visibility is insufficient"],
            )
        return OpeningMatch(
            reference_id,
            None,
            QCStatus.REVIEW_REQUIRED,
            None,
            None,
            ["no acceptable candidate near the expected position"],
        )

    eligible.sort(key=lambda item: item[0])
    best_cost, best = eligible[0]

    if best_cost > accept_cost:
        return OpeningMatch(
            reference_id,
            None,
            QCStatus.CHANGE_CANDIDATE,
            best_cost,
            None,
            ["nearest candidate exceeds the accepted geometric cost"],
        )

    margin = None
    if len(eligible) > 1:
        margin = eligible[1][0] - best_cost
        if margin < ambiguity_margin:
            return OpeningMatch(
                reference_id,
                best.candidate_id,
                QCStatus.REVIEW_REQUIRED,
                best_cost,
                margin,
                ["best and second-best candidates are too similar"],
            )

    return OpeningMatch(
        reference_id,
        best.candidate_id,
        QCStatus.CLEAR,
        best_cost,
        margin,
        ["single acceptable local correspondence"],
    )
