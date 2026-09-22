from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from geometry_guardian.features.correspondence import CorrespondenceSet
from geometry_guardian.features.quality import (
    CorrespondenceQuality,
    evaluate_correspondence_quality,
)
from geometry_guardian.registration.provider_gate import (
    ProviderRegistrationResult,
    register_correspondence_set,
)


@dataclass(slots=True)
class ProviderBenchmarkResult:
    provider_name: str
    extractor_name: str | None
    matcher_name: str | None
    match_count: int
    score_median: float | None
    score_min: float | None
    score_max: float | None
    region_evaluable_matches: int
    wrong_neighbor_matches: int
    wrong_neighbor_fraction: float | None
    correspondence_quality: CorrespondenceQuality
    registration: ProviderRegistrationResult


def _score_stats(matches: CorrespondenceSet) -> tuple[float | None, float | None, float | None]:
    values = [
        float(m.score)
        for m in matches.correspondences
        if m.score is not None
    ]
    if not values:
        return None, None, None
    return float(median(values)), float(min(values)), float(max(values))


def _wrong_neighbor_stats(matches: CorrespondenceSet) -> tuple[int, int, float | None]:
    evaluable = 0
    wrong = 0

    for match in matches.correspondences:
        if match.reference_region_id is None or match.after_region_id is None:
            continue
        evaluable += 1
        if match.reference_region_id != match.after_region_id:
            wrong += 1

    fraction = None if evaluable == 0 else wrong / evaluable
    return evaluable, wrong, fraction


def benchmark_correspondence_set(
    matches: CorrespondenceSet,
    *,
    min_match_count: int = 12,
    min_spatial_coverage_fraction: float = 0.25,
    min_bbox_fraction: float = 0.20,
    **registration_kwargs,
) -> ProviderBenchmarkResult:
    """Evaluate one already-produced provider output.

    Runtime/VRAM are intentionally not measured here because this function works
    on a neutral CorrespondenceSet. Runtime harnesses can attach those values as
    external benchmark metadata later.
    """
    score_median, score_min, score_max = _score_stats(matches)
    evaluable, wrong, wrong_fraction = _wrong_neighbor_stats(matches)

    quality = evaluate_correspondence_quality(
        matches,
        min_match_count=min_match_count,
        min_spatial_coverage_fraction=min_spatial_coverage_fraction,
        min_bbox_fraction=min_bbox_fraction,
    )
    registration = register_correspondence_set(
        matches,
        min_match_count=min_match_count,
        min_spatial_coverage_fraction=min_spatial_coverage_fraction,
        min_bbox_fraction=min_bbox_fraction,
        **registration_kwargs,
    )

    return ProviderBenchmarkResult(
        provider_name=matches.provider.name,
        extractor_name=matches.provider.detector,
        matcher_name=matches.provider.matcher,
        match_count=len(matches.correspondences),
        score_median=score_median,
        score_min=score_min,
        score_max=score_max,
        region_evaluable_matches=evaluable,
        wrong_neighbor_matches=wrong,
        wrong_neighbor_fraction=wrong_fraction,
        correspondence_quality=quality,
        registration=registration,
    )
