from geometry_guardian.evidence.fusion import EvidenceSignal, fuse_evidence
from geometry_guardian.qc.statuses import QCStatus


def test_two_independent_clear_channels_can_clear():
    decision = fuse_evidence([
        EvidenceSignal("contours", QCStatus.CLEAR),
        EvidenceSignal("lines", QCStatus.CLEAR),
    ])
    assert decision.status == QCStatus.CLEAR


def test_one_change_channel_requires_review_not_fail():
    decision = fuse_evidence([
        EvidenceSignal("contours", QCStatus.CHANGE_CANDIDATE),
        EvidenceSignal("lines", QCStatus.CLEAR),
    ])
    assert decision.status == QCStatus.REVIEW_REQUIRED


def test_two_change_channels_make_change_candidate():
    decision = fuse_evidence([
        EvidenceSignal("contours", QCStatus.CHANGE_CANDIDATE),
        EvidenceSignal("lines", QCStatus.CHANGE_CANDIDATE),
    ])
    assert decision.status == QCStatus.CHANGE_CANDIDATE


def test_duplicate_same_channel_does_not_double_vote():
    decision = fuse_evidence([
        EvidenceSignal("contours", QCStatus.CHANGE_CANDIDATE),
        EvidenceSignal("contours", QCStatus.CHANGE_CANDIDATE),
        EvidenceSignal("lines", QCStatus.CLEAR),
    ])
    assert decision.status == QCStatus.REVIEW_REQUIRED
    assert decision.change_weight == 1.0


def test_one_clear_channel_is_insufficient():
    decision = fuse_evidence([
        EvidenceSignal("contours", QCStatus.CLEAR),
    ])
    assert decision.status == QCStatus.INSUFFICIENT_DATA
