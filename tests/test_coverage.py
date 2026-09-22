from geometry_guardian.qc.coverage import facade_status, summarize_statuses
from geometry_guardian.qc.statuses import QCStatus


def test_clear_requires_minimum_coverage():
    statuses = [QCStatus.CLEAR] * 8 + [QCStatus.INSUFFICIENT_DATA] * 2
    summary = summarize_statuses(statuses)
    assert summary.fraction_verified == 0.8
    assert facade_status(summary, minimum_coverage=0.8) == QCStatus.CLEAR


def test_low_coverage_cannot_be_clear():
    statuses = [QCStatus.CLEAR] * 7 + [QCStatus.INSUFFICIENT_DATA] * 3
    summary = summarize_statuses(statuses)
    assert facade_status(summary, minimum_coverage=0.8) == QCStatus.INSUFFICIENT_DATA


def test_change_candidate_has_priority():
    statuses = [QCStatus.CLEAR] * 9 + [QCStatus.CHANGE_CANDIDATE]
    summary = summarize_statuses(statuses)
    assert facade_status(summary) == QCStatus.CHANGE_CANDIDATE
