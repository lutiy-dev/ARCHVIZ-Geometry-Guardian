from geometry_guardian.features import (
    Correspondence,
    CorrespondenceSet,
    FeatureProviderInfo,
)
from geometry_guardian.registration import (
    FrameRegistrationStatus,
    register_correspondence_set,
)


def _set(points):
    return CorrespondenceSet(
        provider=FeatureProviderInfo("synthetic"),
        reference_image_size=(1280, 736),
        after_image_size=(1280, 736),
        correspondences=[
            Correspondence(ref, aft, reference_feature_id=i, after_feature_id=i)
            for i, (ref, aft) in enumerate(points)
        ],
    )


def test_good_spatial_support_reaches_ransac():
    points = []
    for y in (60, 220, 420, 620):
        for x in (80, 360, 700, 1100):
            points.append(((x, y), (x + 5, y - 3)))

    result = register_correspondence_set(
        _set(points),
        max_translation_px=10,
    )
    assert result.registration.status == FrameRegistrationStatus.VERIFIED


def test_cluster_is_rejected_before_ransac():
    points = [
        ((100 + i, 120 + i % 2), (102 + i, 119 + i % 2))
        for i in range(20)
    ]
    result = register_correspondence_set(_set(points))
    assert result.registration.status == FrameRegistrationStatus.INSUFFICIENT_DATA
    assert result.registration.transform is None
