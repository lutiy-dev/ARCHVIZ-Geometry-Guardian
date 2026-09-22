from __future__ import annotations

from dataclasses import dataclass

from .statuses import QCStatus


@dataclass(slots=True)
class CoverageSummary:
    reference_total: int
    verified: int
    review_required: int
    insufficient_data: int
    change_candidates: int

    @property
    def fraction_verified(self) -> float | None:
        if self.reference_total == 0:
            return None
        return self.verified / self.reference_total


def summarize_statuses(statuses: list[QCStatus]) -> CoverageSummary:
    return CoverageSummary(
        reference_total=len(statuses),
        verified=sum(s == QCStatus.CLEAR for s in statuses),
        review_required=sum(s == QCStatus.REVIEW_REQUIRED for s in statuses),
        insufficient_data=sum(s == QCStatus.INSUFFICIENT_DATA for s in statuses),
        change_candidates=sum(s == QCStatus.CHANGE_CANDIDATE for s in statuses),
    )


def facade_status(
    summary: CoverageSummary,
    *,
    minimum_coverage: float = 0.8,
) -> QCStatus:
    if summary.reference_total == 0:
        return QCStatus.INSUFFICIENT_DATA
    if summary.change_candidates:
        return QCStatus.CHANGE_CANDIDATE
    if summary.review_required:
        return QCStatus.REVIEW_REQUIRED
    coverage = summary.fraction_verified or 0.0
    if coverage < minimum_coverage:
        return QCStatus.INSUFFICIENT_DATA
    return QCStatus.CLEAR
