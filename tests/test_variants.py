from geometry_guardian.benchmark import (
    ControlledVariantSpec,
    GeometryExpectation,
    VariantChangeType,
    validate_variant_spec,
)


CORE = (
    "camera_pose",
    "projection",
    "building_silhouette",
    "facade_grid",
    "major_openings",
)


def test_day_night_preservation_spec_is_valid():
    spec = ControlledVariantSpec(
        variant_id="night::dev",
        category="day_night",
        reference_image="before.png",
        after_image="night.png",
        geometry_expectation=GeometryExpectation.PRESERVED,
        changed_properties=(
            VariantChangeType.LIGHTING,
            VariantChangeType.DAY_NIGHT,
        ),
        invariant_properties=CORE,
        controlled_change_description="Relight only.",
    )
    result = validate_variant_spec(spec)
    assert result.valid is True
    assert result.errors == []


def test_preservation_case_cannot_intend_geometry_change():
    spec = ControlledVariantSpec(
        variant_id="bad::dev",
        category="appearance_change",
        reference_image="before.png",
        after_image="after.png",
        geometry_expectation=GeometryExpectation.PRESERVED,
        changed_properties=(VariantChangeType.GEOMETRY,),
        invariant_properties=CORE,
        controlled_change_description="Bad spec.",
    )
    result = validate_variant_spec(spec)
    assert result.valid is False
    assert any("cannot list geometry" in e for e in result.errors)


def test_geometry_change_requires_known_geometry_flag():
    spec = ControlledVariantSpec(
        variant_id="geometry::dev",
        category="geometry_change",
        reference_image="before.png",
        after_image="after.png",
        geometry_expectation=GeometryExpectation.CHANGED,
        changed_properties=(VariantChangeType.GEOMETRY,),
        invariant_properties=("camera_pose", "projection"),
        controlled_change_description="Move W017.",
        known_changed_element_ids=("W017",),
    )
    result = validate_variant_spec(spec)
    assert result.valid is True


def test_camera_mismatch_requires_camera_change():
    spec = ControlledVariantSpec(
        variant_id="camera::dev",
        category="camera_mismatch",
        reference_image="before.png",
        after_image="after.png",
        geometry_expectation=GeometryExpectation.UNKNOWN,
        changed_properties=(VariantChangeType.APPEARANCE,),
        invariant_properties=(),
        controlled_change_description="Wrong declaration.",
    )
    result = validate_variant_spec(spec)
    assert result.valid is False
    assert any("camera" in e for e in result.errors)
