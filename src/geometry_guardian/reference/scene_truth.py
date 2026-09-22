from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SceneReferenceStatus(str, Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    CONFLICT = "conflict"


@dataclass(slots=True)
class SceneReferenceEvidence:
    scene_version: str | None = None
    camera_name: str | None = None
    frame: int | None = None
    render_width: int | None = None
    render_height: int | None = None
    crop: tuple[int, int, int, int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SceneReferenceValidation:
    status: SceneReferenceStatus
    reasons: list[str]
    usable_for_enrichment: bool


def validate_scene_reference(
    evidence: SceneReferenceEvidence,
    *,
    before_width: int,
    before_height: int,
    expected_scene_version: str | None = None,
    expected_camera_name: str | None = None,
) -> SceneReferenceValidation:
    reasons: list[str] = []
    hard_conflict = False
    partial = False

    if evidence.render_width is None or evidence.render_height is None:
        reasons.append("scene render dimensions are unknown")
        partial = True
    elif (evidence.render_width, evidence.render_height) != (before_width, before_height):
        reasons.append(
            f"render dimensions {evidence.render_width}x{evidence.render_height} "
            f"do not match BEFORE {before_width}x{before_height}"
        )
        hard_conflict = True

    if expected_scene_version is not None:
        if evidence.scene_version is None:
            reasons.append("scene version is unknown")
            partial = True
        elif evidence.scene_version != expected_scene_version:
            reasons.append(
                f"scene version mismatch: {evidence.scene_version!r} != "
                f"{expected_scene_version!r}"
            )
            hard_conflict = True

    if expected_camera_name is not None:
        if evidence.camera_name is None:
            reasons.append("camera name is unknown")
            partial = True
        elif evidence.camera_name != expected_camera_name:
            reasons.append(
                f"camera mismatch: {evidence.camera_name!r} != {expected_camera_name!r}"
            )
            hard_conflict = True

    if hard_conflict:
        return SceneReferenceValidation(
            SceneReferenceStatus.CONFLICT, reasons, usable_for_enrichment=False
        )
    if partial:
        return SceneReferenceValidation(
            SceneReferenceStatus.PARTIALLY_VERIFIED,
            reasons,
            usable_for_enrichment=True,
        )
    return SceneReferenceValidation(
        SceneReferenceStatus.VERIFIED,
        ["scene reference matches the known BEFORE metadata"],
        usable_for_enrichment=True,
    )
