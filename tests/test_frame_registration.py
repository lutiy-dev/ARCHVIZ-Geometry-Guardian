import numpy as np

from geometry_guardian.registration.frame import (
    FrameRegistrationStatus,
    estimate_frame_registration,
)


def _grid_points() -> np.ndarray:
    xs, ys = np.meshgrid(
        np.linspace(50, 550, 5),
        np.linspace(40, 340, 4),
    )
    return np.column_stack([xs.ravel(), ys.ravel()]).astype(np.float32)


def test_identity_registration_is_verified():
    ref = _grid_points()
    result = estimate_frame_registration(ref, ref.copy())

    assert result.status == FrameRegistrationStatus.VERIFIED
    assert result.transform is not None
    assert abs(result.transform.scale - 1.0) < 1e-6
    assert result.transform.translation_magnitude_px < 1e-5
    assert result.inlier_fraction == 1.0


def test_small_global_translation_is_reported_and_allowed():
    ref = _grid_points()
    aft = ref + np.array([8.0, -5.0], dtype=np.float32)

    result = estimate_frame_registration(
        ref,
        aft,
        max_translation_px=12.0,
    )

    assert result.status == FrameRegistrationStatus.VERIFIED
    assert result.transform is not None
    assert abs(result.transform.translation_x_px - 8.0) < 0.1
    assert abs(result.transform.translation_y_px + 5.0) < 0.1


def test_large_translation_requires_review():
    ref = _grid_points()
    aft = ref + np.array([35.0, 0.0], dtype=np.float32)

    result = estimate_frame_registration(
        ref,
        aft,
        max_translation_px=20.0,
    )

    assert result.status == FrameRegistrationStatus.REVIEW_REQUIRED


def test_large_scale_requires_review():
    ref = _grid_points()
    aft = ref * 1.05

    result = estimate_frame_registration(
        ref,
        aft,
        max_scale_delta=0.02,
    )

    assert result.status == FrameRegistrationStatus.REVIEW_REQUIRED


def test_too_few_correspondences_is_insufficient():
    ref = _grid_points()[:4]
    result = estimate_frame_registration(ref, ref.copy())

    assert result.status == FrameRegistrationStatus.INSUFFICIENT_DATA


def test_outlier_heavy_correspondences_are_insufficient():
    ref = _grid_points()
    aft = ref.copy()
    aft[8:] = aft[8:] + np.array([100.0, 70.0], dtype=np.float32)

    result = estimate_frame_registration(
        ref,
        aft,
        min_inlier_fraction=0.7,
    )

    assert result.status == FrameRegistrationStatus.INSUFFICIENT_DATA
