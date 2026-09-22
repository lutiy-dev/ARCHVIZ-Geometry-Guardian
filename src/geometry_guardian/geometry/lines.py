from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot

import cv2
import numpy as np

from geometry_guardian.qc.statuses import QCStatus


@dataclass(frozen=True, slots=True)
class LineSegment:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def length(self) -> float:
        return hypot(self.x2 - self.x1, self.y2 - self.y1)

    @property
    def midpoint(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) * 0.5, (self.y1 + self.y2) * 0.5)

    @property
    def angle_deg(self) -> float:
        angle = degrees(atan2(self.y2 - self.y1, self.x2 - self.x1)) % 180.0
        return angle


@dataclass(slots=True)
class LineMatch:
    reference_index: int
    candidate_index: int | None
    status: QCStatus
    cost: float | None
    ambiguity_margin: float | None
    angle_delta_deg: float | None
    midpoint_distance_px: float | None
    length_ratio: float | None
    reasons: list[str]


def _to_gray_u8(image: np.ndarray) -> np.ndarray:
    arr = np.asarray(image)
    if arr.ndim == 2:
        gray = arr
    elif arr.ndim == 3 and arr.shape[2] in (3, 4):
        if arr.shape[2] == 4:
            arr = arr[..., :3]
        if arr.dtype != np.uint8:
            if np.issubdtype(arr.dtype, np.floating) and float(arr.max()) <= 1.0:
                arr = arr * 255.0
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    else:
        raise ValueError("image must be HxW, HxWx3, or HxWx4")

    if gray.dtype != np.uint8:
        if np.issubdtype(gray.dtype, np.floating) and float(gray.max()) <= 1.0:
            gray = gray * 255.0
        gray = np.clip(gray, 0, 255).astype(np.uint8)
    return gray


def detect_lsd_lines(
    image: np.ndarray,
    *,
    min_length_px: float = 20.0,
    roi_mask: np.ndarray | None = None,
) -> list[LineSegment]:
    """Detect line segments using OpenCV LSD.

    This is intentionally the simple baseline. DeepLSD can be benchmarked later
    without changing the downstream LineSegment interface.
    """
    gray = _to_gray_u8(image)
    detector = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    detected = detector.detect(gray)[0]

    if detected is None:
        return []

    mask = None
    if roi_mask is not None:
        mask = np.asarray(roi_mask).astype(bool)
        if mask.shape != gray.shape:
            raise ValueError("roi_mask shape must match image height/width")

    result: list[LineSegment] = []
    for raw in detected.reshape(-1, 4):
        line = LineSegment(*(float(v) for v in raw))
        if line.length < min_length_px:
            continue

        if mask is not None:
            mx, my = line.midpoint
            ix = int(round(mx))
            iy = int(round(my))
            if not (0 <= ix < mask.shape[1] and 0 <= iy < mask.shape[0]):
                continue
            if not mask[iy, ix]:
                continue

        result.append(line)

    return result


def _angle_delta(a: float, b: float) -> float:
    diff = abs(a - b) % 180.0
    return min(diff, 180.0 - diff)


def _line_cost(
    reference: LineSegment,
    candidate: LineSegment,
    *,
    search_radius_px: float,
    angle_tolerance_deg: float,
) -> tuple[float, float, float, float]:
    angle_delta = _angle_delta(reference.angle_deg, candidate.angle_deg)
    rmx, rmy = reference.midpoint
    cmx, cmy = candidate.midpoint
    midpoint_distance = hypot(cmx - rmx, cmy - rmy)

    length_ratio = max(
        candidate.length / max(reference.length, 1e-6),
        reference.length / max(candidate.length, 1e-6),
    )

    angle_term = angle_delta / max(angle_tolerance_deg, 1e-6)
    position_term = midpoint_distance / max(search_radius_px, 1e-6)
    length_term = abs(candidate.length - reference.length) / max(reference.length, 1e-6)

    cost = 0.45 * angle_term + 0.35 * position_term + 0.20 * length_term
    return cost, angle_delta, midpoint_distance, length_ratio


def match_reference_line(
    reference: LineSegment,
    candidates: list[LineSegment],
    *,
    reference_index: int = 0,
    search_radius_px: float = 30.0,
    angle_tolerance_deg: float = 8.0,
    max_length_ratio: float = 1.8,
    accept_cost: float = 0.7,
    ambiguity_margin: float = 0.08,
) -> LineMatch:
    eligible: list[tuple[float, int, float, float, float]] = []

    for index, candidate in enumerate(candidates):
        cost, angle_delta, midpoint_distance, length_ratio = _line_cost(
            reference,
            candidate,
            search_radius_px=search_radius_px,
            angle_tolerance_deg=angle_tolerance_deg,
        )

        if midpoint_distance > search_radius_px:
            continue
        if angle_delta > angle_tolerance_deg:
            continue
        if length_ratio > max_length_ratio:
            continue

        eligible.append(
            (cost, index, angle_delta, midpoint_distance, length_ratio)
        )

    if not eligible:
        return LineMatch(
            reference_index,
            None,
            QCStatus.REVIEW_REQUIRED,
            None,
            None,
            None,
            None,
            None,
            ["no acceptable line candidate near the expected segment"],
        )

    eligible.sort(key=lambda item: item[0])
    best = eligible[0]
    best_cost, best_index, angle_delta, midpoint_distance, length_ratio = best

    if best_cost > accept_cost:
        return LineMatch(
            reference_index,
            None,
            QCStatus.CHANGE_CANDIDATE,
            best_cost,
            None,
            angle_delta,
            midpoint_distance,
            length_ratio,
            ["nearest structural line exceeds the accepted cost"],
        )

    margin = None
    if len(eligible) > 1:
        margin = eligible[1][0] - best_cost
        if margin < ambiguity_margin:
            return LineMatch(
                reference_index,
                best_index,
                QCStatus.REVIEW_REQUIRED,
                best_cost,
                margin,
                angle_delta,
                midpoint_distance,
                length_ratio,
                ["best and second-best line candidates are too similar"],
            )

    return LineMatch(
        reference_index,
        best_index,
        QCStatus.CLEAR,
        best_cost,
        margin,
        angle_delta,
        midpoint_distance,
        length_ratio,
        ["single acceptable local structural-line correspondence"],
    )
