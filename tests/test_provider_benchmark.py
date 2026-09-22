from geometry_guardian.benchmark import benchmark_correspondence_set
from geometry_guardian.features import (
    Correspondence,
    CorrespondenceSet,
    FeatureProviderInfo,
)
from geometry_guardian.features.quality import QualityStatus
from geometry_guardian.registration import FrameRegistrationStatus


def _spread_correspondences(*, wrong_regions: set[int] | None = None):
    wrong_regions = wrong_regions or set()
    matches = []
    index = 0

    for y in (60, 220, 420, 620):
        for x in (80, 360, 700, 1100):
            ref_region = f"W{index:03d}"
            aft_region = (
                f"W{index + 1:03d}" if index in wrong_regions else ref_region
            )
            matches.append(
                Correspondence(
                    reference_xy=(x, y),
                    after_xy=(x + 4, y - 2),
                    score=0.9 - index * 0.005,
                    reference_feature_id=index,
                    after_feature_id=index,
                    reference_region_id=ref_region,
                    after_region_id=aft_region,
                )
            )
            index += 1

    return CorrespondenceSet(
        provider=FeatureProviderInfo(
            name="synthetic",
            detector="synthetic-keypoints",
            matcher="synthetic-matcher",
        ),
        reference_image_size=(1280, 736),
        after_image_size=(1280, 736),
        correspondences=matches,
    )


def test_benchmark_reports_clean_identity_regions():
    result = benchmark_correspondence_set(
        _spread_correspondences(),
        max_translation_px=10,
    )

    assert result.match_count == 16
    assert result.region_evaluable_matches == 16
    assert result.wrong_neighbor_matches == 0
    assert result.wrong_neighbor_fraction == 0.0
    assert result.correspondence_quality.status == QualityStatus.PASS
    assert result.registration.registration.status == FrameRegistrationStatus.VERIFIED


def test_benchmark_exposes_wrong_neighbor_aliasing_even_when_ransac_is_good():
    result = benchmark_correspondence_set(
        _spread_correspondences(wrong_regions={3, 7, 11, 15}),
        max_translation_px=10,
    )

    # Numerically the point transform is still excellent...
    assert result.registration.registration.status == FrameRegistrationStatus.VERIFIED
    # ...but semantic repeated-element identity is wrong for 25% of evaluated matches.
    assert result.wrong_neighbor_matches == 4
    assert result.wrong_neighbor_fraction == 0.25


def test_score_summary_is_reported():
    result = benchmark_correspondence_set(_spread_correspondences())
    assert result.score_median is not None
    assert result.score_min is not None
    assert result.score_max is not None
    assert result.score_min <= result.score_median <= result.score_max
