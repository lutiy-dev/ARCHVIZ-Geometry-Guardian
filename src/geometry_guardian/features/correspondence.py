from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class FeatureProviderInfo:
    name: str
    version: str | None = None
    detector: str | None = None
    matcher: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Correspondence:
    reference_xy: tuple[float, float]
    after_xy: tuple[float, float]
    score: float | None = None
    reference_feature_id: str | int | None = None
    after_feature_id: str | int | None = None
    reference_region_id: str | None = None
    after_region_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CorrespondenceSet:
    provider: FeatureProviderInfo
    reference_image_size: tuple[int, int]
    after_image_size: tuple[int, int]
    correspondences: list[Correspondence]
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        rw, rh = self.reference_image_size
        aw, ah = self.after_image_size
        if rw <= 0 or rh <= 0 or aw <= 0 or ah <= 0:
            errors.append("image sizes must be positive")

        for index, match in enumerate(self.correspondences):
            rx, ry = match.reference_xy
            ax, ay = match.after_xy
            if not (0 <= rx < rw and 0 <= ry < rh):
                errors.append(f"match {index}: reference point outside image")
            if not (0 <= ax < aw and 0 <= ay < ah):
                errors.append(f"match {index}: after point outside image")
            if match.score is not None and not np.isfinite(match.score):
                errors.append(f"match {index}: score must be finite")

        return errors

    def reference_points(self) -> np.ndarray:
        return np.asarray(
            [m.reference_xy for m in self.correspondences],
            dtype=np.float32,
        ).reshape(-1, 2)

    def after_points(self) -> np.ndarray:
        return np.asarray(
            [m.after_xy for m in self.correspondences],
            dtype=np.float32,
        ).reshape(-1, 2)

    def scores(self) -> np.ndarray:
        return np.asarray(
            [np.nan if m.score is None else float(m.score) for m in self.correspondences],
            dtype=np.float32,
        )
