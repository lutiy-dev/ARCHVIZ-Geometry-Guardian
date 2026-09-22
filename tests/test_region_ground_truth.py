from geometry_guardian.benchmark import (
    PairRegionGroundTruth,
    RegionPolygon,
    assign_region_ground_truth,
    region_at_point,
)
from geometry_guardian.features import (
    Correspondence,
    CorrespondenceSet,
    FeatureProviderInfo,
)


def _gt():
    return PairRegionGroundTruth(
        reference_regions=(
            RegionPolygon("W001", ((10, 10), (40, 10), (40, 60), (10, 60))),
            RegionPolygon("W002", ((50, 10), (80, 10), (80, 60), (50, 60))),
        ),
        after_regions=(
            RegionPolygon("W001", ((12, 10), (42, 10), (42, 60), (12, 60))),
            RegionPolygon("W002", ((52, 10), (82, 10), (82, 60), (52, 60))),
        ),
    )


def test_region_at_point_returns_stable_id():
    gt = _gt()
    assert region_at_point((20, 20), gt.reference_regions) == "W001"
    assert region_at_point((60, 20), gt.reference_regions) == "W002"
    assert region_at_point((95, 20), gt.reference_regions) is None


def test_region_annotation_exposes_neighbor_jump():
    matches = CorrespondenceSet(
        provider=FeatureProviderInfo("synthetic"),
        reference_image_size=(100, 80),
        after_image_size=(100, 80),
        correspondences=[
            Correspondence((20, 20), (22, 20)),
            Correspondence((60, 20), (22, 20)),
        ],
    )

    annotated = assign_region_ground_truth(matches, _gt())

    assert annotated.correspondences[0].reference_region_id == "W001"
    assert annotated.correspondences[0].after_region_id == "W001"
    assert annotated.correspondences[1].reference_region_id == "W002"
    assert annotated.correspondences[1].after_region_id == "W001"


def test_overlapping_gt_is_treated_as_ambiguous():
    regions = (
        RegionPolygon("A", ((0, 0), (50, 0), (50, 50), (0, 50))),
        RegionPolygon("B", ((20, 0), (70, 0), (70, 50), (20, 50))),
    )
    assert region_at_point((30, 20), regions) is None
