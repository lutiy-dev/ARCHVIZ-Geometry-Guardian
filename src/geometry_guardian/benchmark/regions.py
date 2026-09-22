from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import cv2
import numpy as np

from geometry_guardian.features.correspondence import Correspondence, CorrespondenceSet


@dataclass(frozen=True, slots=True)
class RegionPolygon:
    region_id: str
    polygon_xy: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class PairRegionGroundTruth:
    reference_regions: tuple[RegionPolygon, ...]
    after_regions: tuple[RegionPolygon, ...]


def load_pair_region_ground_truth(path: str | Path) -> PairRegionGroundTruth:
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    def parse(items):
        result = []
        for raw in items:
            polygon = tuple(
                (float(point[0]), float(point[1]))
                for point in raw["polygon_xy"]
            )
            if len(polygon) < 3:
                raise ValueError(
                    f"region {raw['region_id']!r} polygon must have >= 3 points"
                )
            result.append(
                RegionPolygon(
                    region_id=str(raw["region_id"]),
                    polygon_xy=polygon,
                )
            )
        return tuple(result)

    return PairRegionGroundTruth(
        reference_regions=parse(data.get("reference_regions", [])),
        after_regions=parse(data.get("after_regions", [])),
    )


def region_at_point(
    point_xy: tuple[float, float],
    regions: tuple[RegionPolygon, ...],
) -> str | None:
    point = (float(point_xy[0]), float(point_xy[1]))
    hits: list[str] = []

    for region in regions:
        contour = np.asarray(region.polygon_xy, dtype=np.float32)
        inside = cv2.pointPolygonTest(contour, point, False)
        if inside >= 0:
            hits.append(region.region_id)

    if not hits:
        return None
    if len(hits) > 1:
        # Ambiguous overlapping GT should not be silently resolved.
        return None
    return hits[0]


def assign_region_ground_truth(
    matches: CorrespondenceSet,
    ground_truth: PairRegionGroundTruth,
) -> CorrespondenceSet:
    annotated: list[Correspondence] = []

    for match in matches.correspondences:
        annotated.append(
            Correspondence(
                reference_xy=match.reference_xy,
                after_xy=match.after_xy,
                score=match.score,
                reference_feature_id=match.reference_feature_id,
                after_feature_id=match.after_feature_id,
                reference_region_id=region_at_point(
                    match.reference_xy,
                    ground_truth.reference_regions,
                ),
                after_region_id=region_at_point(
                    match.after_xy,
                    ground_truth.after_regions,
                ),
                metadata=dict(match.metadata),
            )
        )

    return CorrespondenceSet(
        provider=matches.provider,
        reference_image_size=matches.reference_image_size,
        after_image_size=matches.after_image_size,
        correspondences=annotated,
        metadata=dict(matches.metadata),
    )
