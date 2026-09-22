from geometry_guardian.features import (
    Correspondence,
    CorrespondenceSet,
    FeatureProviderInfo,
    QualityStatus,
    evaluate_correspondence_quality,
)


def _spread_matches() -> CorrespondenceSet:
    points = []
    index = 0
    for y in (50, 200, 350, 500):
        for x in (80, 320, 640, 960):
            points.append(
                Correspondence(
                    (x, y),
                    (x + 2, y - 1),
                    score=0.9,
                    reference_feature_id=index,
                    after_feature_id=index,
                )
            )
            index += 1
    return CorrespondenceSet(
        provider=FeatureProviderInfo("synthetic"),
        reference_image_size=(1280, 736),
        after_image_size=(1280, 736),
        correspondences=points,
    )


def test_spread_matches_pass_quality_gate():
    result = evaluate_correspondence_quality(_spread_matches())
    assert result.status == QualityStatus.PASS
    assert result.spatial_coverage_fraction >= 0.25


def test_clustered_matches_are_insufficient_for_global_registration():
    matches = CorrespondenceSet(
        provider=FeatureProviderInfo("synthetic"),
        reference_image_size=(1280, 736),
        after_image_size=(1280, 736),
        correspondences=[
            Correspondence((100 + i, 100 + i % 3), (102 + i, 99 + i % 3))
            for i in range(20)
        ],
    )
    result = evaluate_correspondence_quality(matches)
    assert result.status == QualityStatus.INSUFFICIENT


def test_duplicate_feature_ids_warn():
    matches = _spread_matches()
    first = matches.correspondences[0]
    matches.correspondences[1] = Correspondence(
        matches.correspondences[1].reference_xy,
        matches.correspondences[1].after_xy,
        reference_feature_id=first.reference_feature_id,
        after_feature_id=first.after_feature_id,
    )
    matches.correspondences[2] = Correspondence(
        matches.correspondences[2].reference_xy,
        matches.correspondences[2].after_xy,
        reference_feature_id=first.reference_feature_id,
        after_feature_id=first.after_feature_id,
    )

    result = evaluate_correspondence_quality(
        matches,
        max_duplicate_feature_fraction=0.05,
    )
    assert result.status == QualityStatus.WARN
