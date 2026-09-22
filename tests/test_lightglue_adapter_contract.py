import numpy as np
import pytest

from geometry_guardian.features.providers.lightglue_provider import (
    LightGlueProviderConfig,
    _validate_config,
    build_correspondence_set,
)


def test_build_correspondence_set_preserves_indices_and_scores():
    ref = np.array([[10, 20], [30, 40], [50, 60]], dtype=np.float32)
    aft = np.array([[12, 19], [32, 39], [52, 59]], dtype=np.float32)
    matches = np.array([[0, 0], [2, 2]], dtype=np.int64)
    scores = np.array([0.91, 0.83], dtype=np.float32)

    result = build_correspondence_set(
        provider_name="cvg/LightGlue",
        extractor_name="aliked",
        reference_image_size=(100, 80),
        after_image_size=(100, 80),
        reference_keypoints=ref,
        after_keypoints=aft,
        match_indices=matches,
        scores=scores,
    )

    assert result.validate() == []
    assert len(result.correspondences) == 2
    assert result.correspondences[0].reference_feature_id == 0
    assert result.correspondences[1].reference_feature_id == 2
    assert abs(result.correspondences[0].score - 0.91) < 1e-5


def test_bad_match_index_is_rejected():
    with pytest.raises(ValueError):
        build_correspondence_set(
            provider_name="cvg/LightGlue",
            extractor_name="aliked",
            reference_image_size=(100, 80),
            after_image_size=(100, 80),
            reference_keypoints=np.array([[10, 20]], dtype=np.float32),
            after_keypoints=np.array([[10, 20]], dtype=np.float32),
            match_indices=np.array([[3, 0]], dtype=np.int64),
        )


def test_superpoint_is_blocked_by_default_for_license_safety():
    with pytest.raises(ValueError, match="restrictive license"):
        _validate_config(LightGlueProviderConfig(extractor="superpoint"))


def test_aliked_is_allowed_by_default():
    _validate_config(LightGlueProviderConfig(extractor="aliked"))
