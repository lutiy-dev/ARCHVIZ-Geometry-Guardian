import cv2
import numpy as np

from geometry_guardian.benchmark import (
    PairRegionGroundTruth,
    RegionPolygon,
    render_gt_previews,
    write_gt_previews,
)


def _image(path):
    image = np.zeros((100, 160, 3), dtype=np.uint8)
    image[:] = 40
    assert cv2.imwrite(str(path), image)


def _gt():
    return PairRegionGroundTruth(
        reference_regions=(
            RegionPolygon("W001", ((20, 20), (60, 20), (60, 70), (20, 70))),
        ),
        after_regions=(
            RegionPolygon("W001", ((22, 21), (62, 21), (62, 71), (22, 71))),
        ),
    )


def test_render_gt_previews_changes_pixels(tmp_path):
    ref = tmp_path / "ref.png"
    aft = tmp_path / "aft.png"
    _image(ref)
    _image(aft)

    ref_preview, aft_preview = render_gt_previews(
        _gt(),
        reference_image_path=ref,
        after_image_path=aft,
    )

    original = cv2.imread(str(ref), cv2.IMREAD_COLOR)
    assert np.any(ref_preview != original)
    assert np.any(aft_preview != original)


def test_write_gt_previews_creates_files(tmp_path):
    ref = tmp_path / "ref.png"
    aft = tmp_path / "aft.png"
    _image(ref)
    _image(aft)

    ref_out = tmp_path / "out" / "ref_preview.png"
    aft_out = tmp_path / "out" / "aft_preview.png"

    write_gt_previews(
        _gt(),
        reference_image_path=ref,
        after_image_path=aft,
        reference_output_path=ref_out,
        after_output_path=aft_out,
    )

    assert ref_out.exists()
    assert aft_out.exists()
    assert cv2.imread(str(ref_out)) is not None
    assert cv2.imread(str(aft_out)) is not None
