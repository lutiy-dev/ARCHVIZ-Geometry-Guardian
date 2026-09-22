from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .regions import PairRegionGroundTruth, RegionPolygon


@dataclass(frozen=True, slots=True)
class GTPreviewStyle:
    line_thickness: int = 2
    label_scale: float = 0.5
    label_thickness: int = 1
    draw_centers: bool = True


def _load_bgr(path: str | Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"cannot decode image: {path}")
    return image


def _draw_regions(
    image: np.ndarray,
    regions: tuple[RegionPolygon, ...],
    *,
    style: GTPreviewStyle,
) -> np.ndarray:
    canvas = image.copy()

    for region in regions:
        points = np.asarray(region.polygon_xy, dtype=np.int32).reshape(-1, 1, 2)
        if len(points) < 3:
            continue

        cv2.polylines(
            canvas,
            [points],
            isClosed=True,
            color=(255, 255, 255),
            thickness=style.line_thickness,
            lineType=cv2.LINE_AA,
        )

        moments = cv2.moments(points)
        if abs(moments["m00"]) > 1e-6:
            cx = int(round(moments["m10"] / moments["m00"]))
            cy = int(round(moments["m01"] / moments["m00"]))
        else:
            raw = points.reshape(-1, 2)
            cx = int(round(float(raw[:, 0].mean())))
            cy = int(round(float(raw[:, 1].mean())))

        if style.draw_centers:
            cv2.circle(canvas, (cx, cy), 3, (255, 255, 255), -1, cv2.LINE_AA)

        text = region.region_id
        (tw, th), baseline = cv2.getTextSize(
            text,
            cv2.FONT_HERSHEY_SIMPLEX,
            style.label_scale,
            style.label_thickness,
        )
        x = max(0, min(cx - tw // 2, canvas.shape[1] - tw - 1))
        y = max(th + 2, min(cy - 6, canvas.shape[0] - baseline - 1))

        cv2.rectangle(
            canvas,
            (x - 2, y - th - 2),
            (x + tw + 2, y + baseline + 2),
            (0, 0, 0),
            -1,
        )
        cv2.putText(
            canvas,
            text,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            style.label_scale,
            (255, 255, 255),
            style.label_thickness,
            cv2.LINE_AA,
        )

    return canvas


def render_gt_previews(
    gt: PairRegionGroundTruth,
    *,
    reference_image_path: str | Path,
    after_image_path: str | Path,
    style: GTPreviewStyle | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    style = style or GTPreviewStyle()
    reference = _load_bgr(reference_image_path)
    after = _load_bgr(after_image_path)

    return (
        _draw_regions(reference, gt.reference_regions, style=style),
        _draw_regions(after, gt.after_regions, style=style),
    )


def write_gt_previews(
    gt: PairRegionGroundTruth,
    *,
    reference_image_path: str | Path,
    after_image_path: str | Path,
    reference_output_path: str | Path,
    after_output_path: str | Path,
    style: GTPreviewStyle | None = None,
) -> None:
    reference_preview, after_preview = render_gt_previews(
        gt,
        reference_image_path=reference_image_path,
        after_image_path=after_image_path,
        style=style,
    )

    reference_output = Path(reference_output_path)
    after_output = Path(after_output_path)
    reference_output.parent.mkdir(parents=True, exist_ok=True)
    after_output.parent.mkdir(parents=True, exist_ok=True)

    if not cv2.imwrite(str(reference_output), reference_preview):
        raise OSError(f"failed to write preview: {reference_output}")
    if not cv2.imwrite(str(after_output), after_preview):
        raise OSError(f"failed to write preview: {after_output}")
