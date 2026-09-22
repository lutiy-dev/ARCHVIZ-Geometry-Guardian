import csv
import json

import cv2
import numpy as np
import pytest

from geometry_guardian.benchmark import (
    load_region_box_csv,
    rows_to_ground_truth,
    validate_ground_truth_against_images,
    write_ground_truth_json,
    write_region_box_csv_template,
)


def _write_image(path, width=200, height=120):
    image = np.zeros((height, width, 3), dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def _fill_template(path, count=10):
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    for index, row in enumerate(rows[:count]):
        x1 = 5 + index * 15
        row.update(
            {
                "ref_x1": str(x1),
                "ref_y1": "10",
                "ref_x2": str(x1 + 10),
                "ref_y2": "40",
                "aft_x1": str(x1 + 2),
                "aft_y1": "11",
                "aft_x2": str(x1 + 12),
                "aft_y2": "41",
            }
        )

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows[:count])


def test_csv_gt_roundtrip_and_image_validation(tmp_path):
    table = tmp_path / "windows.csv"
    write_region_box_csv_template(table, region_count=10)
    _fill_template(table, count=10)

    rows = load_region_box_csv(table)
    gt = rows_to_ground_truth(rows)

    ref = tmp_path / "ref.png"
    aft = tmp_path / "aft.png"
    _write_image(ref)
    _write_image(aft)

    errors = validate_ground_truth_against_images(
        gt,
        reference_image_path=ref,
        after_image_path=aft,
        minimum_common_ids=10,
    )
    assert errors == []

    output = tmp_path / "gt.json"
    write_ground_truth_json(gt, output, source_csv=str(table))
    data = json.loads(output.read_text(encoding="utf-8"))
    assert len(data["reference_regions"]) == 10
    assert data["reference_regions"][0]["region_id"] == "W001"


def test_partial_rectangle_is_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    write_region_box_csv_template(path, region_count=1)

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys())

    rows[0]["ref_x1"] = "10"
    rows[0]["ref_y1"] = "10"

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="incomplete ref rectangle"):
        load_region_box_csv(path)


def test_out_of_bounds_annotation_is_rejected(tmp_path):
    table = tmp_path / "windows.csv"
    write_region_box_csv_template(table, region_count=10)
    _fill_template(table, count=10)

    rows = load_region_box_csv(table)
    # Replace last item with an out-of-bounds box while retaining IDs.
    last = rows[-1]
    rows[-1] = type(last)(
        region_id=last.region_id,
        reference_xyxy=(190, 10, 230, 40),
        after_xyxy=last.after_xyxy,
        notes=last.notes,
    )
    gt = rows_to_ground_truth(rows)

    ref = tmp_path / "ref.png"
    aft = tmp_path / "aft.png"
    _write_image(ref)
    _write_image(aft)

    errors = validate_ground_truth_against_images(
        gt,
        reference_image_path=ref,
        after_image_path=aft,
        minimum_common_ids=10,
    )
    assert any("outside" in error for error in errors)
