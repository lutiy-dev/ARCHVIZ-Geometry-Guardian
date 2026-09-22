from geometry_guardian.matching.openings import (
    CandidateOpening,
    match_reference_opening,
)
from geometry_guardian.qc.statuses import QCStatus


def test_local_match_clear():
    result = match_reference_opening(
        reference_id="W017",
        facade_id="F01",
        expected_bbox=(100, 100, 160, 220),
        candidates=[
            CandidateOpening("A17", "F01", (102, 101, 162, 221)),
            CandidateOpening("A18", "F01", (300, 100, 360, 220)),
        ],
        search_radius_px=80,
    )
    assert result.status == QCStatus.CLEAR
    assert result.candidate_id == "A17"


def test_ambiguous_candidates_require_review():
    result = match_reference_opening(
        reference_id="W017",
        facade_id="F01",
        expected_bbox=(100, 100, 160, 220),
        candidates=[
            CandidateOpening("A17", "F01", (102, 100, 162, 220)),
            CandidateOpening("A18", "F01", (103, 100, 163, 220)),
        ],
        search_radius_px=80,
        ambiguity_margin=0.05,
    )
    assert result.status == QCStatus.REVIEW_REQUIRED


def test_low_visibility_is_insufficient_data():
    result = match_reference_opening(
        reference_id="W017",
        facade_id="F01",
        expected_bbox=(100, 100, 160, 220),
        candidates=[
            CandidateOpening(
                "A17",
                "F01",
                (102, 100, 162, 220),
                visibility=0.1,
            )
        ],
        search_radius_px=80,
    )
    assert result.status == QCStatus.INSUFFICIENT_DATA
