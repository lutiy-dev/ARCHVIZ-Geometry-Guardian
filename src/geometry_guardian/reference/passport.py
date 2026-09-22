from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class VerificationState(str, Enum):
    VERIFIED = "verified"
    HUMAN_VERIFIED = "human_verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    CONFLICT = "conflict"


class CapabilityState(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    LIMITED = "limited"


@dataclass(slots=True)
class PropertyEvidence:
    value: Any
    source: str
    verification: VerificationState = VerificationState.UNVERIFIED
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["verification"] = self.verification.value
        return data


@dataclass(slots=True)
class ReferenceElement:
    element_id: str
    element_type: str
    facade_id: str | None = None
    identity: PropertyEvidence | None = None
    reference_outline: PropertyEvidence | None = None
    expected_projection: PropertyEvidence | None = None
    bbox_xyxy: PropertyEvidence | None = None
    neighbors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "element_type": self.element_type,
            "facade_id": self.facade_id,
            "identity": self.identity.to_dict() if self.identity else None,
            "reference_outline": self.reference_outline.to_dict() if self.reference_outline else None,
            "expected_projection": self.expected_projection.to_dict() if self.expected_projection else None,
            "bbox_xyxy": self.bbox_xyxy.to_dict() if self.bbox_xyxy else None,
            "neighbors": list(self.neighbors),
            "tags": list(self.tags),
        }


@dataclass
class ReferencePassport:
    passport_id: str
    reference_image_id: str
    image_width: int
    image_height: int
    elements: list[ReferenceElement] = field(default_factory=list)
    facade_regions: dict[str, PropertyEvidence] = field(default_factory=dict)
    exclusions: list[PropertyEvidence] = field(default_factory=list)
    capabilities: dict[str, CapabilityState] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def element_by_id(self, element_id: str) -> ReferenceElement:
        for element in self.elements:
            if element.element_id == element_id:
                return element
        raise KeyError(element_id)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.image_width <= 0 or self.image_height <= 0:
            errors.append("reference image dimensions must be positive")

        ids = [e.element_id for e in self.elements]
        if len(ids) != len(set(ids)):
            errors.append("element_id values must be unique")

        known = set(ids)
        for element in self.elements:
            missing = [n for n in element.neighbors if n not in known]
            if missing:
                errors.append(
                    f"{element.element_id}: unknown neighbor IDs: {', '.join(missing)}"
                )

        return errors

    def infer_capabilities(self) -> dict[str, CapabilityState]:
        caps = dict(self.capabilities)

        caps.setdefault(
            "silhouette_check",
            CapabilityState.AVAILABLE
            if "silhouette" in self.facade_regions
            else CapabilityState.UNAVAILABLE,
        )

        opening_elements = [
            e for e in self.elements if e.element_type in {"window", "door", "opening"}
        ]
        opening_ready = [
            e for e in opening_elements
            if e.bbox_xyxy is not None or e.reference_outline is not None
        ]
        if not opening_elements:
            caps.setdefault("opening_geometry_check", CapabilityState.UNAVAILABLE)
        elif len(opening_ready) == len(opening_elements):
            caps.setdefault("opening_geometry_check", CapabilityState.AVAILABLE)
        else:
            caps.setdefault("opening_geometry_check", CapabilityState.LIMITED)

        return caps

    def reference_completeness(self, element_type: str | None = None) -> dict[str, float | int | None]:
        selected = [
            e for e in self.elements
            if element_type is None or e.element_type == element_type
        ]
        if not selected:
            return {"known": 0, "geometry_ready": 0, "fraction": None}

        ready = sum(
            1 for e in selected
            if e.bbox_xyxy is not None or e.reference_outline is not None
        )
        return {
            "known": len(selected),
            "geometry_ready": ready,
            "fraction": ready / len(selected),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "passport_id": self.passport_id,
            "reference_image_id": self.reference_image_id,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "elements": [e.to_dict() for e in self.elements],
            "facade_regions": {
                key: value.to_dict() for key, value in self.facade_regions.items()
            },
            "exclusions": [e.to_dict() for e in self.exclusions],
            "capabilities": {
                key: value.value for key, value in self.infer_capabilities().items()
            },
            "limitations": list(self.limitations),
            "metadata": dict(self.metadata),
        }
