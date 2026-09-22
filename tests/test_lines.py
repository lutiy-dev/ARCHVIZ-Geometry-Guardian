import numpy as np
import cv2

from geometry_guardian.geometry.lines import (
    LineSegment,
    detect_lsd_lines,
    match_reference_line,
)
from geometry_guardian.qc.statuses import QCStatus


def test_lsd_detects_long_architectural_lines():
    image = np.zeros((160, 220, 3), dtype=np.uint8)
    cv2.line(image, (20, 40), (200, 40), (255, 255, 255), 2)
    cv2.line(image, (30, 20), (30, 140), (255, 255, 255), 2)

    lines = detect_lsd_lines(image, min_length_px=60)
    assert len(lines) >= 2


def test_reference_line_matches_local_candidate():
    reference = LineSegment(20, 40, 200, 40)
    candidates = [
        LineSegment(21, 42, 201, 42),
        LineSegment(20, 100, 200, 100),
    ]
    result = match_reference_line(
        reference,
        candidates,
        search_radius_px=20,
        angle_tolerance_deg=5,
    )

    assert result.status == QCStatus.CLEAR
    assert result.candidate_index == 0


def test_wrong_orientation_is_not_forced():
    reference = LineSegment(20, 40, 200, 40)
    candidates = [LineSegment(100, 10, 100, 140)]
    result = match_reference_line(
        reference,
        candidates,
        search_radius_px=100,
        angle_tolerance_deg=5,
    )

    assert result.status == QCStatus.REVIEW_REQUIRED
    assert result.candidate_index is None


def test_two_similar_lines_are_ambiguous():
    reference = LineSegment(20, 40, 200, 40)
    candidates = [
        LineSegment(20, 42, 200, 42),
        LineSegment(20, 43, 200, 43),
    ]
    result = match_reference_line(
        reference,
        candidates,
        search_radius_px=20,
        angle_tolerance_deg=5,
        ambiguity_margin=0.1,
    )

    assert result.status == QCStatus.REVIEW_REQUIRED
