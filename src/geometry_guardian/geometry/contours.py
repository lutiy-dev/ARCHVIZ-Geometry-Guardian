from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(slots=True)
class ContourDistanceMetrics:
    reference_edge_pixels: int
    after_edge_pixels: int
    reference_to_after_median_px: float | None
    reference_to_after_p95_px: float | None
    after_to_reference_median_px: float | None
    after_to_reference_p95_px: float | None
    symmetric_median_px: float | None
    symmetric_p95_px: float | None
    reference_supported_fraction: float | None
    after_supported_fraction: float | None
    symmetric_supported_fraction: float | None


def _to_gray_u8(image: np.ndarray) -> np.ndarray:
    arr = np.asarray(image)
    if arr.ndim == 2:
        gray = arr
    elif arr.ndim == 3 and arr.shape[2] in (3, 4):
        if arr.shape[2] == 4:
            arr = arr[..., :3]
        if arr.dtype != np.uint8:
            arr = _to_u8(arr)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    else:
        raise ValueError("image must be HxW, HxWx3, or HxWx4")

    return _to_u8(gray)


def _to_u8(arr: np.ndarray) -> np.ndarray:
    a = np.asarray(arr)
    if a.dtype == np.uint8:
        return a
    if np.issubdtype(a.dtype, np.floating):
        finite = np.isfinite(a)
        if not finite.all():
            a = np.where(finite, a, 0)
        max_value = float(a.max()) if a.size else 0.0
        if max_value <= 1.0:
            a = a * 255.0
    return np.clip(a, 0, 255).astype(np.uint8)


def detect_edges(
    image: np.ndarray,
    *,
    low_threshold: float = 80.0,
    high_threshold: float = 160.0,
    gaussian_sigma: float = 1.0,
    roi_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Return a boolean Canny edge map.

    The optional ROI is applied after edge extraction so that edges at the mask
    boundary are not introduced by masking the image itself.
    """
    gray = _to_gray_u8(image)

    if gaussian_sigma > 0:
        gray = cv2.GaussianBlur(gray, (0, 0), gaussian_sigma)

    edges = cv2.Canny(
        gray,
        threshold1=float(low_threshold),
        threshold2=float(high_threshold),
        L2gradient=True,
    ) > 0

    if roi_mask is not None:
        mask = np.asarray(roi_mask).astype(bool)
        if mask.shape != edges.shape:
            raise ValueError("roi_mask shape must match image height/width")
        edges &= mask

    return edges


def _distance_to_edges(edge_map: np.ndarray) -> np.ndarray:
    edges = np.asarray(edge_map).astype(bool)
    if edges.ndim != 2:
        raise ValueError("edge_map must be 2D")

    # distanceTransform computes distance for non-zero pixels to nearest zero.
    # Therefore edge pixels become zeros and all other pixels ones.
    non_edges = (~edges).astype(np.uint8)
    return cv2.distanceTransform(non_edges, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)


def _directed_metrics(
    source_edges: np.ndarray,
    target_distance: np.ndarray,
    support_threshold_px: float,
) -> tuple[float | None, float | None, float | None, np.ndarray]:
    source = np.asarray(source_edges).astype(bool)
    distances = target_distance[source]
    if distances.size == 0:
        return None, None, None, distances

    median = float(np.median(distances))
    p95 = float(np.percentile(distances, 95))
    supported = float(np.mean(distances <= support_threshold_px))
    return median, p95, supported, distances


def compare_edge_maps(
    reference_edges: np.ndarray,
    after_edges: np.ndarray,
    *,
    support_threshold_px: float = 2.0,
) -> ContourDistanceMetrics:
    """Symmetric contour comparison.

    This deliberately measures geometry evidence only. It does not decide
    whether an edge came from architecture, a shadow, reflection, or texture.
    That interpretation belongs to the evidence-fusion layer.
    """
    ref = np.asarray(reference_edges).astype(bool)
    aft = np.asarray(after_edges).astype(bool)

    if ref.shape != aft.shape:
        raise ValueError("reference_edges and after_edges must have equal shape")
    if ref.ndim != 2:
        raise ValueError("edge maps must be 2D")

    ref_count = int(ref.sum())
    aft_count = int(aft.sum())

    if ref_count == 0 or aft_count == 0:
        return ContourDistanceMetrics(
            reference_edge_pixels=ref_count,
            after_edge_pixels=aft_count,
            reference_to_after_median_px=None,
            reference_to_after_p95_px=None,
            after_to_reference_median_px=None,
            after_to_reference_p95_px=None,
            symmetric_median_px=None,
            symmetric_p95_px=None,
            reference_supported_fraction=None,
            after_supported_fraction=None,
            symmetric_supported_fraction=None,
        )

    dist_to_aft = _distance_to_edges(aft)
    dist_to_ref = _distance_to_edges(ref)

    r_med, r_p95, r_support, r_dist = _directed_metrics(
        ref, dist_to_aft, support_threshold_px
    )
    a_med, a_p95, a_support, a_dist = _directed_metrics(
        aft, dist_to_ref, support_threshold_px
    )

    combined = np.concatenate([r_dist, a_dist])
    return ContourDistanceMetrics(
        reference_edge_pixels=ref_count,
        after_edge_pixels=aft_count,
        reference_to_after_median_px=r_med,
        reference_to_after_p95_px=r_p95,
        after_to_reference_median_px=a_med,
        after_to_reference_p95_px=a_p95,
        symmetric_median_px=float(np.median(combined)),
        symmetric_p95_px=float(np.percentile(combined, 95)),
        reference_supported_fraction=r_support,
        after_supported_fraction=a_support,
        symmetric_supported_fraction=float((r_support + a_support) * 0.5),
    )
