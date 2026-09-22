from __future__ import annotations

from dataclasses import dataclass, field

from geometry_guardian.qc.statuses import QCStatus


@dataclass(frozen=True, slots=True)
class EvidenceSignal:
    channel: str
    status: QCStatus
    weight: float = 1.0
    reason: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class EvidenceDecision:
    status: QCStatus
    clear_weight: float
    change_weight: float
    review_weight: float
    insufficient_weight: float
    used_channels: list[str]
    reasons: list[str]


def fuse_evidence(
    signals: list[EvidenceSignal],
    *,
    minimum_clear_weight: float = 2.0,
    minimum_change_weight: float = 2.0,
) -> EvidenceDecision:
    """Fuse independent evidence with transparent conservative rules.

    This is intentionally not a probability model.

    Rules:
    - no evidence => INSUFFICIENT_DATA;
    - enough independent change evidence => CHANGE_CANDIDATE;
    - any unresolved review evidence => REVIEW_REQUIRED unless change threshold won;
    - enough clear evidence with no change/review conflict => CLEAR;
    - otherwise => INSUFFICIENT_DATA.

    Signals with the same channel are collapsed by taking the strongest status
    contribution for that channel, preventing one algorithm from voting many
    times merely because it emitted many measurements.
    """
    if not signals:
        return EvidenceDecision(
            QCStatus.INSUFFICIENT_DATA,
            0.0,
            0.0,
            0.0,
            0.0,
            [],
            ["no evidence channels were supplied"],
        )

    severity = {
        QCStatus.CHANGE_CANDIDATE: 4,
        QCStatus.REVIEW_REQUIRED: 3,
        QCStatus.INSUFFICIENT_DATA: 2,
        QCStatus.NOT_VERIFIED: 2,
        QCStatus.CLEAR: 1,
    }

    by_channel: dict[str, EvidenceSignal] = {}
    for signal in signals:
        current = by_channel.get(signal.channel)
        if current is None or severity[signal.status] > severity[current.status]:
            by_channel[signal.channel] = signal
        elif severity[signal.status] == severity[current.status] and signal.weight > current.weight:
            by_channel[signal.channel] = signal

    clear_weight = 0.0
    change_weight = 0.0
    review_weight = 0.0
    insufficient_weight = 0.0
    reasons: list[str] = []

    for signal in by_channel.values():
        weight = max(float(signal.weight), 0.0)
        if signal.status == QCStatus.CLEAR:
            clear_weight += weight
        elif signal.status == QCStatus.CHANGE_CANDIDATE:
            change_weight += weight
        elif signal.status == QCStatus.REVIEW_REQUIRED:
            review_weight += weight
        elif signal.status in (QCStatus.INSUFFICIENT_DATA, QCStatus.NOT_VERIFIED):
            insufficient_weight += weight

        if signal.reason:
            reasons.append(f"{signal.channel}: {signal.reason}")

    if change_weight >= minimum_change_weight:
        status = QCStatus.CHANGE_CANDIDATE
    elif change_weight > 0 or review_weight > 0:
        status = QCStatus.REVIEW_REQUIRED
    elif clear_weight >= minimum_clear_weight:
        status = QCStatus.CLEAR
    else:
        status = QCStatus.INSUFFICIENT_DATA

    return EvidenceDecision(
        status=status,
        clear_weight=clear_weight,
        change_weight=change_weight,
        review_weight=review_weight,
        insufficient_weight=insufficient_weight,
        used_channels=sorted(by_channel),
        reasons=reasons,
    )
