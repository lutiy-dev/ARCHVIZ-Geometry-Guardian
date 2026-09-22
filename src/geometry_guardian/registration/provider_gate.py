from __future__ import annotations

from dataclasses import dataclass

from geometry_guardian.features.correspondence import CorrespondenceSet
from geometry_guardian.features.quality import (
    CorrespondenceQuality,
    QualityStatus,
    evaluate_correspondence_quality,
)
from .frame import FrameRegistrationResult, FrameRegistrationStatus, estimate_frame_registration


@dataclass(slots=True)
class ProviderRegistrationResult:
    correspondence_quality: CorrespondenceQuality
    registration: FrameRegistrationResult


def register_correspondence_set(
    matches: CorrespondenceSet,
    *,
    min_match_count: int = 12,
    min_spatial_coverage_fraction: float = 0.25,
    min_bbox_fraction: float = 0.20,
    **registration_kwargs,
) -> ProviderRegistrationResult:
    quality = evaluate_correspondence_quality(
        matches,
        min_match_count=min_match_count,
        min_spatial_coverage_fraction=min_spatial_coverage_fraction,
        min_bbox_fraction=min_bbox_fraction,
    )

    if quality.status == QualityStatus.INSUFFICIENT:
        registration = FrameRegistrationResult(
            status=FrameRegistrationStatus.INSUFFICIENT_DATA,
            transform=None,
            correspondence_count=len(matches.correspondences),
            inlier_count=0,
            inlier_fraction=None,
            median_inlier_residual_px=None,
            reasons=[
                "feature-provider gate rejected correspondences before RANSAC",
                *quality.reasons,
            ],
        )
        return ProviderRegistrationResult(quality, registration)

    registration = estimate_frame_registration(
        matches.reference_points(),
        matches.after_points(),
        min_correspondences=min_match_count,
        **registration_kwargs,
    )

    if quality.status == QualityStatus.WARN and registration.status == FrameRegistrationStatus.VERIFIED:
        registration.status = FrameRegistrationStatus.REVIEW_REQUIRED
        registration.reasons.append(
            "feature-provider quality warning prevents automatic VERIFIED"
        )

    return ProviderRegistrationResult(quality, registration)
