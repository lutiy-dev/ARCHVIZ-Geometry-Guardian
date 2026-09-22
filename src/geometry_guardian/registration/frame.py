from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan2, degrees, hypot

import cv2
import numpy as np


class FrameRegistrationStatus(str, Enum):
    VERIFIED = "verified"
    REVIEW_REQUIRED = "review_required"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class SimilarityTransform:
    scale: float
    rotation_deg: float
    translation_x_px: float
    translation_y_px: float
    matrix_2x3: tuple[tuple[float, float, float], tuple[float, float, float]]

    @property
    def translation_magnitude_px(self) -> float:
        return hypot(self.translation_x_px, self.translation_y_px)


@dataclass(slots=True)
class FrameRegistrationResult:
    status: FrameRegistrationStatus
    transform: SimilarityTransform | None
    correspondence_count: int
    inlier_count: int
    inlier_fraction: float | None
    median_inlier_residual_px: float | None
    reasons: list[str]


def _decode_similarity(matrix: np.ndarray) -> SimilarityTransform:
    a, b, tx = (float(v) for v in matrix[0])
    c, d, ty = (float(v) for v in matrix[1])

    # estimateAffinePartial2D returns a similarity-like matrix:
    # [ a -b tx ]
    # [ b  a ty ]
    scale = (hypot(a, c) + hypot(b, d)) * 0.5
    rotation = degrees(atan2(c, a))

    return SimilarityTransform(
        scale=scale,
        rotation_deg=rotation,
        translation_x_px=tx,
        translation_y_px=ty,
        matrix_2x3=((a, b, tx), (c, d, ty)),
    )


def _transform_points(points: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    homogeneous = np.concatenate(
        [points.astype(np.float64), np.ones((len(points), 1), dtype=np.float64)],
        axis=1,
    )
    return homogeneous @ matrix.T


def estimate_frame_registration(
    reference_points: np.ndarray,
    after_points: np.ndarray,
    *,
    ransac_reproj_threshold_px: float = 2.5,
    min_correspondences: int = 8,
    min_inlier_fraction: float = 0.60,
    max_translation_px: float = 20.0,
    max_scale_delta: float = 0.02,
    max_rotation_deg: float = 0.5,
) -> FrameRegistrationResult:
    """Estimate and validate a global similarity transform.

    This module does NOT detect correspondences and does NOT warp the AFTER
    image. It only evaluates a proposed set of point correspondences and reports
    the technical correction implied by them.

    Feature providers such as SuperPoint+LightGlue can be plugged in later.
    """
    ref = np.asarray(reference_points, dtype=np.float32)
    aft = np.asarray(after_points, dtype=np.float32)

    if ref.shape != aft.shape or ref.ndim != 2 or ref.shape[1:] != (2,):
        raise ValueError("reference_points and after_points must both be Nx2")
    if len(ref) < min_correspondences:
        return FrameRegistrationResult(
            FrameRegistrationStatus.INSUFFICIENT_DATA,
            None,
            len(ref),
            0,
            None,
            None,
            [f"need at least {min_correspondences} correspondences"],
        )

    matrix, inlier_mask = cv2.estimateAffinePartial2D(
        ref,
        aft,
        method=cv2.RANSAC,
        ransacReprojThreshold=float(ransac_reproj_threshold_px),
        maxIters=5000,
        confidence=0.999,
        refineIters=10,
    )

    if matrix is None or inlier_mask is None:
        return FrameRegistrationResult(
            FrameRegistrationStatus.INSUFFICIENT_DATA,
            None,
            len(ref),
            0,
            0.0,
            None,
            ["RANSAC could not estimate a stable global similarity transform"],
        )

    inliers = inlier_mask.reshape(-1).astype(bool)
    inlier_count = int(inliers.sum())
    inlier_fraction = inlier_count / len(ref)

    transform = _decode_similarity(matrix)
    predicted = _transform_points(ref, matrix)
    residuals = np.linalg.norm(predicted - aft, axis=1)
    median_residual = (
        float(np.median(residuals[inliers])) if inlier_count else None
    )

    reasons: list[str] = []
    if inlier_fraction < min_inlier_fraction:
        reasons.append(
            f"inlier fraction {inlier_fraction:.3f} < {min_inlier_fraction:.3f}"
        )

    if transform.translation_magnitude_px > max_translation_px:
        reasons.append(
            "global translation exceeds allowed technical correction: "
            f"{transform.translation_magnitude_px:.2f}px > {max_translation_px:.2f}px"
        )

    scale_delta = abs(transform.scale - 1.0)
    if scale_delta > max_scale_delta:
        reasons.append(
            f"scale delta {scale_delta:.5f} > {max_scale_delta:.5f}"
        )

    if abs(transform.rotation_deg) > max_rotation_deg:
        reasons.append(
            f"rotation {transform.rotation_deg:.3f}deg exceeds "
            f"{max_rotation_deg:.3f}deg"
        )

    if inlier_fraction < min_inlier_fraction:
        status = FrameRegistrationStatus.INSUFFICIENT_DATA
    elif reasons:
        status = FrameRegistrationStatus.REVIEW_REQUIRED
    else:
        status = FrameRegistrationStatus.VERIFIED
        reasons.append("global frame registration is within configured limits")

    return FrameRegistrationResult(
        status=status,
        transform=transform,
        correspondence_count=len(ref),
        inlier_count=inlier_count,
        inlier_fraction=inlier_fraction,
        median_inlier_residual_px=median_residual,
        reasons=reasons,
    )
