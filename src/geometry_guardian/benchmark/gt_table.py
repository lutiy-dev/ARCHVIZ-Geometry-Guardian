from __future__ import annotations

from dataclasses import dataclass
import csv
import json
from pathlib import Path
from typing import Iterable

import cv2

from .regions import PairRegionGroundTruth, RegionPolygon


@dataclass(frozen=True, slots=True)
class RegionBoxRow:
    region_id: str
    reference_xyxy: tuple[float, float, float, float] | None
    after_xyxy: tuple[float, float, float, float] | None
    notes: str = ""


CSV_COLUMNS = (
    "region_id",
    "ref_x1",
    "ref_y1",
    "ref_x2",
    "ref_y2",
    "aft_x1",
    "aft_y1",
    "aft_x2",
    "aft_y2",
    "notes",
)


def _parse_box(row: dict[str, str], prefix: str) -> tuple[float, float, float, float] | None:
    keys = [f"{prefix}_x1", f"{prefix}_y1", f"{prefix}_x2", f"{prefix}_y2"]
    values = [str(row.get(key, "")).strip() for key in keys]

    if all(value == "" for value in values):
        return None
    if any(value == "" for value in values):
        raise ValueError(f"incomplete {prefix} rectangle; fill all four coordinates or leave all blank")

    x1, y1, x2, y2 = (float(value) for value in values)
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"invalid {prefix} rectangle: expected x2>x1 and y2>y1")
    return (x1, y1, x2, y2)


def load_region_box_csv(path: str | Path) -> list[RegionBoxRow]:
    rows: list[RegionBoxRow] = []
    seen: set[str] = set()

    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in CSV_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("CSV missing columns: " + ", ".join(missing))

        for line_number, raw in enumerate(reader, start=2):
            region_id = str(raw.get("region_id", "")).strip()
            if not region_id:
                raise ValueError(f"line {line_number}: region_id is required")
            if region_id in seen:
                raise ValueError(f"line {line_number}: duplicate region_id {region_id!r}")
            seen.add(region_id)

            try:
                ref_box = _parse_box(raw, "ref")
                aft_box = _parse_box(raw, "aft")
            except ValueError as exc:
                raise ValueError(f"line {line_number} ({region_id}): {exc}") from exc

            if ref_box is None and aft_box is None:
                raise ValueError(
                    f"line {line_number} ({region_id}): at least one side must be annotated"
                )

            rows.append(
                RegionBoxRow(
                    region_id=region_id,
                    reference_xyxy=ref_box,
                    after_xyxy=aft_box,
                    notes=str(raw.get("notes", "")).strip(),
                )
            )

    return rows


def _box_to_polygon(box: tuple[float, float, float, float]) -> tuple[tuple[float, float], ...]:
    x1, y1, x2, y2 = box
    return ((x1, y1), (x2, y1), (x2, y2), (x1, y2))


def rows_to_ground_truth(rows: Iterable[RegionBoxRow]) -> PairRegionGroundTruth:
    reference: list[RegionPolygon] = []
    after: list[RegionPolygon] = []

    for row in rows:
        if row.reference_xyxy is not None:
            reference.append(
                RegionPolygon(row.region_id, _box_to_polygon(row.reference_xyxy))
            )
        if row.after_xyxy is not None:
            after.append(
                RegionPolygon(row.region_id, _box_to_polygon(row.after_xyxy))
            )

    return PairRegionGroundTruth(tuple(reference), tuple(after))


def validate_ground_truth_against_images(
    gt: PairRegionGroundTruth,
    *,
    reference_image_path: str | Path,
    after_image_path: str | Path,
    minimum_common_ids: int = 10,
) -> list[str]:
    errors: list[str] = []

    ref_image = cv2.imread(str(reference_image_path), cv2.IMREAD_UNCHANGED)
    aft_image = cv2.imread(str(after_image_path), cv2.IMREAD_UNCHANGED)
    if ref_image is None:
        return [f"cannot decode reference image: {reference_image_path}"]
    if aft_image is None:
        return [f"cannot decode AFTER image: {after_image_path}"]

    ref_h, ref_w = ref_image.shape[:2]
    aft_h, aft_w = aft_image.shape[:2]

    def validate_regions(regions, width, height, side):
        ids: set[str] = set()
        for region in regions:
            if region.region_id in ids:
                errors.append(f"{side}: duplicate region_id {region.region_id}")
            ids.add(region.region_id)

            if len(region.polygon_xy) < 3:
                errors.append(f"{side}:{region.region_id}: polygon has <3 points")
                continue

            for x, y in region.polygon_xy:
                if not (0 <= x < width and 0 <= y < height):
                    errors.append(
                        f"{side}:{region.region_id}: point ({x:.2f},{y:.2f}) outside "
                        f"{width}x{height}"
                    )
        return ids

    ref_ids = validate_regions(gt.reference_regions, ref_w, ref_h, "reference")
    aft_ids = validate_regions(gt.after_regions, aft_w, aft_h, "after")
    common = ref_ids & aft_ids

    if len(common) < minimum_common_ids:
        errors.append(
            f"common stable region IDs {len(common)} < required {minimum_common_ids}"
        )

    return errors


def write_ground_truth_json(
    gt: PairRegionGroundTruth,
    path: str | Path,
    *,
    source_csv: str | None = None,
) -> None:
    def encode(regions):
        return [
            {
                "region_id": region.region_id,
                "polygon_xy": [[x, y] for x, y in region.polygon_xy],
            }
            for region in regions
        ]

    payload = {
        "schema_version": "0.1",
        "reference_regions": encode(gt.reference_regions),
        "after_regions": encode(gt.after_regions),
    }
    if source_csv is not None:
        payload["source_csv"] = source_csv

    Path(path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_region_box_csv_template(
    path: str | Path,
    *,
    region_count: int = 20,
    id_prefix: str = "W",
    start_index: int = 1,
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for index in range(start_index, start_index + region_count):
            writer.writerow(
                {
                    "region_id": f"{id_prefix}{index:03d}",
                    "ref_x1": "",
                    "ref_y1": "",
                    "ref_x2": "",
                    "ref_y2": "",
                    "aft_x1": "",
                    "aft_y1": "",
                    "aft_x2": "",
                    "aft_y2": "",
                    "notes": "",
                }
            )
