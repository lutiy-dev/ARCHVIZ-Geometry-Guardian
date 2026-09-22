from geometry_guardian.reference.scene_truth import (
    SceneReferenceEvidence,
    SceneReferenceStatus,
    validate_scene_reference,
)


def test_scene_truth_is_optional_but_can_be_verified():
    result = validate_scene_reference(
        SceneReferenceEvidence(
            scene_version="old_city_v12",
            camera_name="Camera_01",
            render_width=1280,
            render_height=736,
        ),
        before_width=1280,
        before_height=736,
        expected_scene_version="old_city_v12",
        expected_camera_name="Camera_01",
    )
    assert result.status == SceneReferenceStatus.VERIFIED
    assert result.usable_for_enrichment is True


def test_scene_dimension_conflict_disables_enrichment():
    result = validate_scene_reference(
        SceneReferenceEvidence(render_width=1920, render_height=1080),
        before_width=1280,
        before_height=736,
    )
    assert result.status == SceneReferenceStatus.CONFLICT
    assert result.usable_for_enrichment is False
