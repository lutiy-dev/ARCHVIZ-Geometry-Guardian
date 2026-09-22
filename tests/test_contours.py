import numpy as np

from geometry_guardian.geometry.contours import compare_edge_maps, detect_edges


def _rectangle_image(shift_x: int = 0) -> np.ndarray:
    image = np.zeros((120, 160, 3), dtype=np.uint8)
    x1, x2 = 40 + shift_x, 110 + shift_x
    image[30:33, x1:x2] = 255
    image[85:88, x1:x2] = 255
    image[30:88, x1:x1 + 3] = 255
    image[30:88, x2 - 3:x2] = 255
    return image


def test_identical_contours_have_zero_distance():
    image = _rectangle_image()
    edges = detect_edges(image, low_threshold=20, high_threshold=60, gaussian_sigma=0)
    metrics = compare_edge_maps(edges, edges, support_threshold_px=1.0)

    assert metrics.symmetric_median_px == 0.0
    assert metrics.symmetric_p95_px == 0.0
    assert metrics.symmetric_supported_fraction == 1.0


def test_shifted_rectangle_produces_nonzero_contour_distance():
    before = detect_edges(
        _rectangle_image(0),
        low_threshold=20,
        high_threshold=60,
        gaussian_sigma=0,
    )
    after = detect_edges(
        _rectangle_image(6),
        low_threshold=20,
        high_threshold=60,
        gaussian_sigma=0,
    )
    metrics = compare_edge_maps(before, after, support_threshold_px=2.0)

    assert metrics.symmetric_p95_px is not None
    assert metrics.symmetric_p95_px >= 4.0
    assert metrics.symmetric_supported_fraction is not None
    assert metrics.symmetric_supported_fraction < 1.0


def test_empty_edge_map_is_insufficient_measurement():
    empty = np.zeros((20, 20), dtype=bool)
    metrics = compare_edge_maps(empty, empty)
    assert metrics.symmetric_median_px is None
    assert metrics.symmetric_supported_fraction is None
