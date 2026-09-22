from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

import cv2
import numpy as np

from geometry_guardian.benchmark.provider_metrics import (
    ProviderBenchmarkResult,
    benchmark_correspondence_set,
)
from geometry_guardian.features.correspondence import CorrespondenceSet


class FeatureProvider(Protocol):
    def match(
        self,
        reference_image: np.ndarray,
        after_image: np.ndarray,
    ) -> CorrespondenceSet: ...


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    category: str
    reference_path: str
    after_path: str
    expected_geometry_change: bool | None = None
    notes: str = ""


@dataclass(slots=True)
class RuntimeBenchmarkResult:
    case: BenchmarkCase
    provider_name: str
    elapsed_ms: float
    peak_vram_mb: float | None
    metrics: ProviderBenchmarkResult

    def to_dict(self) -> dict[str, Any]:
        registration = self.metrics.registration.registration
        transform = registration.transform
        quality = self.metrics.correspondence_quality

        return {
            "case": asdict(self.case),
            "provider": {
                "name": self.provider_name,
                "extractor": self.metrics.extractor_name,
                "matcher": self.metrics.matcher_name,
            },
            "runtime": {
                "elapsed_ms": self.elapsed_ms,
                "peak_vram_mb": self.peak_vram_mb,
            },
            "matches": {
                "count": self.metrics.match_count,
                "score_median": self.metrics.score_median,
                "score_min": self.metrics.score_min,
                "score_max": self.metrics.score_max,
                "wrong_neighbor_evaluable": self.metrics.region_evaluable_matches,
                "wrong_neighbor_count": self.metrics.wrong_neighbor_matches,
                "wrong_neighbor_fraction": self.metrics.wrong_neighbor_fraction,
            },
            "quality": {
                "status": quality.status.value,
                "occupied_grid_cells": quality.occupied_grid_cells,
                "total_grid_cells": quality.total_grid_cells,
                "spatial_coverage_fraction": quality.spatial_coverage_fraction,
                "reference_bbox_fraction": quality.reference_bbox_fraction,
                "after_bbox_fraction": quality.after_bbox_fraction,
                "duplicate_reference_feature_fraction": quality.duplicate_reference_feature_fraction,
                "duplicate_after_feature_fraction": quality.duplicate_after_feature_fraction,
                "reasons": list(quality.reasons),
            },
            "registration": {
                "status": registration.status.value,
                "correspondence_count": registration.correspondence_count,
                "inlier_count": registration.inlier_count,
                "inlier_fraction": registration.inlier_fraction,
                "median_inlier_residual_px": registration.median_inlier_residual_px,
                "transform": None
                if transform is None
                else {
                    "scale": transform.scale,
                    "rotation_deg": transform.rotation_deg,
                    "translation_x_px": transform.translation_x_px,
                    "translation_y_px": transform.translation_y_px,
                    "translation_magnitude_px": transform.translation_magnitude_px,
                },
                "reasons": list(registration.reasons),
            },
        }


def read_rgb_image(path: str | Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"could not read image: {path}")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def _cuda_peak_memory_mb(provider: FeatureProvider) -> float | None:
    try:
        import torch
    except ModuleNotFoundError:
        return None

    device = getattr(provider, "device", None)
    if device is None or str(device).split(":")[0] != "cuda":
        return None
    if not torch.cuda.is_available():
        return None

    return float(torch.cuda.max_memory_allocated(device=device) / (1024**2))


def run_benchmark_case(
    provider: FeatureProvider,
    case: BenchmarkCase,
    *,
    min_match_count: int = 12,
    min_spatial_coverage_fraction: float = 0.25,
    min_bbox_fraction: float = 0.20,
    **registration_kwargs,
) -> RuntimeBenchmarkResult:
    reference = read_rgb_image(case.reference_path)
    after = read_rgb_image(case.after_path)

    try:
        import torch
    except ModuleNotFoundError:
        torch = None

    device = getattr(provider, "device", None)
    if (
        torch is not None
        and device is not None
        and str(device).split(":")[0] == "cuda"
        and torch.cuda.is_available()
    ):
        torch.cuda.synchronize(device=device)
        torch.cuda.reset_peak_memory_stats(device=device)

    start = perf_counter()
    correspondences = provider.match(reference, after)

    if (
        torch is not None
        and device is not None
        and str(device).split(":")[0] == "cuda"
        and torch.cuda.is_available()
    ):
        torch.cuda.synchronize(device=device)

    elapsed_ms = (perf_counter() - start) * 1000.0
    peak_vram_mb = _cuda_peak_memory_mb(provider)

    metrics = benchmark_correspondence_set(
        correspondences,
        min_match_count=min_match_count,
        min_spatial_coverage_fraction=min_spatial_coverage_fraction,
        min_bbox_fraction=min_bbox_fraction,
        **registration_kwargs,
    )

    return RuntimeBenchmarkResult(
        case=case,
        provider_name=correspondences.provider.name,
        elapsed_ms=elapsed_ms,
        peak_vram_mb=peak_vram_mb,
        metrics=metrics,
    )
