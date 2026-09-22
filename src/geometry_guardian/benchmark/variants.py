from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
from typing import Any


class VariantChangeType(str, Enum):
    NONE = "none"
    APPEARANCE = "appearance"
    LIGHTING = "lighting"
    MATERIAL = "material"
    COLOR = "color"
    DAY_NIGHT = "day_night"
    OCCLUSION = "occlusion"
    TECHNICAL_TRANSFORM = "technical_transform"
    CAMERA = "camera"
    GEOMETRY = "geometry"


class GeometryExpectation(str, Enum):
    PRESERVED = "preserved"
    CHANGED = "changed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ControlledVariantSpec:
    variant_id: str
    category: str
    reference_image: str
    after_image: str
    geometry_expectation: GeometryExpectation
    changed_properties: tuple[VariantChangeType, ...]
    invariant_properties: tuple[str, ...]
    controlled_change_description: str
    creation_method: str = ""
    known_changed_element_ids: tuple[str, ...] = ()
    exclusion_region_ids: tuple[str, ...] = ()
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VariantValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]


PRESERVATION_CATEGORIES = {
    "identity",
    "appearance_change",
    "day_night",
    "repetitive_facade",
    "occlusion",
    "sparse_facade",
    "technical_transform",
}

DEFAULT_ARCHITECTURE_INVARIANTS = (
    "camera_pose",
    "projection",
    "building_silhouette",
    "facade_grid",
    "major_openings",
)


def load_variant_registry(path: str | Path) -> list[ControlledVariantSpec]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = raw.get("variants")
    if not isinstance(items, list):
        raise ValueError("variant registry must contain a 'variants' list")

    result: list[ControlledVariantSpec] = []
    seen: set[str] = set()

    for item in items:
        variant_id = str(item["variant_id"])
        if variant_id in seen:
            raise ValueError(f"duplicate variant_id: {variant_id}")
        seen.add(variant_id)

        result.append(
            ControlledVariantSpec(
                variant_id=variant_id,
                category=str(item["category"]),
                reference_image=str(item["reference_image"]),
                after_image=str(item["after_image"]),
                geometry_expectation=GeometryExpectation(
                    str(item.get("geometry_expectation", "unknown"))
                ),
                changed_properties=tuple(
                    VariantChangeType(str(value))
                    for value in item.get("changed_properties", [])
                ),
                invariant_properties=tuple(
                    str(value) for value in item.get("invariant_properties", [])
                ),
                controlled_change_description=str(
                    item.get("controlled_change_description", "")
                ),
                creation_method=str(item.get("creation_method", "")),
                known_changed_element_ids=tuple(
                    str(value)
                    for value in item.get("known_changed_element_ids", [])
                ),
                exclusion_region_ids=tuple(
                    str(value) for value in item.get("exclusion_region_ids", [])
                ),
                notes=str(item.get("notes", "")),
                metadata=dict(item.get("metadata", {})),
            )
        )

    return result


def validate_variant_spec(spec: ControlledVariantSpec) -> VariantValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not spec.variant_id:
        errors.append("variant_id is required")
    if not spec.category:
        errors.append("category is required")
    if not spec.reference_image:
        errors.append("reference_image is required")
    if not spec.after_image:
        errors.append("after_image is required")
    if not spec.controlled_change_description:
        errors.append("controlled_change_description is required")

    if spec.category in PRESERVATION_CATEGORIES:
        if spec.geometry_expectation != GeometryExpectation.PRESERVED:
            errors.append(
                f"{spec.category} must declare geometry_expectation='preserved'"
            )
        if VariantChangeType.GEOMETRY in spec.changed_properties:
            errors.append(
                f"{spec.category} cannot list geometry as an intended changed property"
            )

    if spec.category == "geometry_change":
        if spec.geometry_expectation != GeometryExpectation.CHANGED:
            errors.append(
                "geometry_change must declare geometry_expectation='changed'"
            )
        if VariantChangeType.GEOMETRY not in spec.changed_properties:
            errors.append(
                "geometry_change must include 'geometry' in changed_properties"
            )
        if not spec.known_changed_element_ids:
            warnings.append(
                "geometry_change has no known_changed_element_ids; localization benchmark will be weak"
            )

    if spec.category == "camera_mismatch":
        if VariantChangeType.CAMERA not in spec.changed_properties:
            errors.append(
                "camera_mismatch must include 'camera' in changed_properties"
            )
        if spec.geometry_expectation != GeometryExpectation.UNKNOWN:
            warnings.append(
                "camera_mismatch normally uses geometry_expectation='unknown' because 2D preservation is not directly comparable"
            )

    if spec.category == "identity":
        unexpected = [
            change for change in spec.changed_properties
            if change != VariantChangeType.NONE
        ]
        if unexpected:
            errors.append("identity may only use changed_properties=['none']")
        if spec.reference_image != spec.after_image:
            warnings.append(
                "identity reference_image and after_image differ; verify they are pixel-identical copies"
            )

    if spec.geometry_expectation == GeometryExpectation.PRESERVED:
        missing = [
            name
            for name in DEFAULT_ARCHITECTURE_INVARIANTS
            if name not in spec.invariant_properties
        ]
        if missing:
            warnings.append(
                "preservation case does not explicitly declare all core invariants: "
                + ", ".join(missing)
            )

    return VariantValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
    )


def validate_variant_registry(
    variants: list[ControlledVariantSpec],
) -> dict[str, VariantValidationResult]:
    return {
        spec.variant_id: validate_variant_spec(spec)
        for spec in variants
    }


def registry_case_ids(variants: list[ControlledVariantSpec]) -> set[str]:
    return {variant.variant_id for variant in variants}
