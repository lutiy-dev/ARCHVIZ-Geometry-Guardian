from geometry_guardian.reference.passport import (
    CapabilityState,
    PropertyEvidence,
    ReferenceElement,
    ReferencePassport,
    VerificationState,
)


def test_reference_passport_is_valid_without_scene_truth():
    p = ReferencePassport(
        passport_id="P001",
        reference_image_id="before.png",
        image_width=1280,
        image_height=736,
        elements=[
            ReferenceElement(
                element_id="W001",
                element_type="window",
                facade_id="F01",
                bbox_xyxy=PropertyEvidence(
                    [100, 100, 200, 250],
                    "image_annotation",
                    VerificationState.HUMAN_VERIFIED,
                ),
            )
        ],
    )

    assert p.validate() == []
    assert p.infer_capabilities()["opening_geometry_check"] == CapabilityState.AVAILABLE
    assert p.reference_completeness("window")["fraction"] == 1.0


def test_duplicate_ids_fail_validation():
    p = ReferencePassport(
        passport_id="P001",
        reference_image_id="before.png",
        image_width=100,
        image_height=100,
        elements=[
            ReferenceElement("W001", "window"),
            ReferenceElement("W001", "window"),
        ],
    )
    assert "element_id values must be unique" in p.validate()
