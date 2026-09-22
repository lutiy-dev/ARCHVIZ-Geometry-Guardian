from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

import numpy as np

from geometry_guardian.features.correspondence import (
    Correspondence,
    CorrespondenceSet,
    FeatureProviderInfo,
)


SUPPORTED_EXTRACTORS = {"aliked", "disk", "sift", "superpoint"}


@dataclass(frozen=True, slots=True)
class LightGlueProviderConfig:
    extractor: str = "aliked"
    max_num_keypoints: int | None = 2048
    filter_threshold: float = 0.1
    depth_confidence: float = 0.95
    width_confidence: float = 0.99
    resize: int | None = None
    device: str = "auto"
    mixed_precision: bool = False
    allow_restricted_superpoint_license: bool = False


def _validate_config(config: LightGlueProviderConfig) -> None:
    if config.extractor not in SUPPORTED_EXTRACTORS:
        raise ValueError(
            f"unsupported extractor {config.extractor!r}; "
            f"expected one of {sorted(SUPPORTED_EXTRACTORS)}"
        )
    if config.extractor == "superpoint" and not config.allow_restricted_superpoint_license:
        raise ValueError(
            "SuperPoint is intentionally blocked by default because its pretrained "
            "implementation/weights use a restrictive license. Set "
            "allow_restricted_superpoint_license=True only after confirming the "
            "intended use is license-compatible."
        )
    if config.max_num_keypoints is not None and config.max_num_keypoints <= 0:
        raise ValueError("max_num_keypoints must be positive or None")
    if not 0 <= config.filter_threshold <= 1:
        raise ValueError("filter_threshold must be in [0, 1]")


def _require_runtime():
    try:
        torch = import_module("torch")
        lightglue = import_module("lightglue")
        utils = import_module("lightglue.utils")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "LightGlue runtime is optional and is not installed. "
            "Install the official cvg/LightGlue package in the environment that "
            "will run this provider."
        ) from exc
    return torch, lightglue, utils


def _to_rgb_float_tensor(image: np.ndarray, torch, device: str):
    arr = np.asarray(image)
    if arr.ndim == 2:
        arr = np.repeat(arr[..., None], 3, axis=2)
    elif arr.ndim == 3 and arr.shape[2] == 4:
        arr = arr[..., :3]
    elif arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError("image must be HxW, HxWx3, or HxWx4")

    if np.issubdtype(arr.dtype, np.floating):
        finite = np.isfinite(arr)
        arr = np.where(finite, arr, 0)
        if arr.size and float(arr.max()) > 1.0:
            arr = arr / 255.0
        arr = np.clip(arr, 0.0, 1.0).astype(np.float32)
    else:
        arr = arr.astype(np.float32) / 255.0

    tensor = torch.from_numpy(arr).permute(2, 0, 1).contiguous()
    return tensor.to(device)


def build_correspondence_set(
    *,
    provider_name: str,
    extractor_name: str,
    reference_image_size: tuple[int, int],
    after_image_size: tuple[int, int],
    reference_keypoints: np.ndarray,
    after_keypoints: np.ndarray,
    match_indices: np.ndarray,
    scores: np.ndarray | None = None,
    provider_metadata: dict[str, Any] | None = None,
) -> CorrespondenceSet:
    """Convert provider outputs into Geometry Guardian's neutral contract."""
    ref_kpts = np.asarray(reference_keypoints, dtype=np.float32).reshape(-1, 2)
    aft_kpts = np.asarray(after_keypoints, dtype=np.float32).reshape(-1, 2)
    pairs = np.asarray(match_indices, dtype=np.int64).reshape(-1, 2)

    if scores is not None:
        score_values = np.asarray(scores, dtype=np.float32).reshape(-1)
        if len(score_values) != len(pairs):
            raise ValueError("scores length must match match_indices length")
    else:
        score_values = None

    correspondences: list[Correspondence] = []
    for index, (ref_index, aft_index) in enumerate(pairs):
        if not (0 <= ref_index < len(ref_kpts)):
            raise ValueError(f"reference match index out of range: {ref_index}")
        if not (0 <= aft_index < len(aft_kpts)):
            raise ValueError(f"after match index out of range: {aft_index}")

        score = None if score_values is None else float(score_values[index])
        correspondences.append(
            Correspondence(
                reference_xy=tuple(float(v) for v in ref_kpts[ref_index]),
                after_xy=tuple(float(v) for v in aft_kpts[aft_index]),
                score=score,
                reference_feature_id=int(ref_index),
                after_feature_id=int(aft_index),
            )
        )

    return CorrespondenceSet(
        provider=FeatureProviderInfo(
            name=provider_name,
            detector=extractor_name,
            matcher="lightglue",
            metadata=dict(provider_metadata or {}),
        ),
        reference_image_size=reference_image_size,
        after_image_size=after_image_size,
        correspondences=correspondences,
        metadata={},
    )


class LightGlueProvider:
    """Optional adapter for the official cvg/LightGlue runtime.

    The core package does not import torch or LightGlue until this provider is
    instantiated/run. This keeps Geometry Guardian's QC core independent from a
    specific feature stack.
    """

    def __init__(self, config: LightGlueProviderConfig | None = None):
        self.config = config or LightGlueProviderConfig()
        _validate_config(self.config)

        torch, lightglue, utils = _require_runtime()
        self._torch = torch
        self._utils = utils

        if self.config.device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            device = self.config.device
        self.device = device

        extractor_classes = {
            "aliked": lightglue.ALIKED,
            "disk": lightglue.DISK,
            "sift": lightglue.SIFT,
            "superpoint": lightglue.SuperPoint,
        }
        extractor_cls = extractor_classes[self.config.extractor]

        extractor_kwargs: dict[str, Any] = {}
        if self.config.max_num_keypoints is not None:
            extractor_kwargs["max_num_keypoints"] = self.config.max_num_keypoints

        self.extractor = extractor_cls(**extractor_kwargs).eval().to(device)
        self.matcher = lightglue.LightGlue(
            features=self.config.extractor,
            filter_threshold=self.config.filter_threshold,
            depth_confidence=self.config.depth_confidence,
            width_confidence=self.config.width_confidence,
            mp=self.config.mixed_precision,
        ).eval().to(device)

    def match(
        self,
        reference_image: np.ndarray,
        after_image: np.ndarray,
    ) -> CorrespondenceSet:
        torch = self._torch
        rbd = self._utils.rbd

        ref_h, ref_w = np.asarray(reference_image).shape[:2]
        aft_h, aft_w = np.asarray(after_image).shape[:2]

        image0 = _to_rgb_float_tensor(reference_image, torch, self.device)
        image1 = _to_rgb_float_tensor(after_image, torch, self.device)

        with torch.inference_mode():
            feats0 = self.extractor.extract(image0, resize=self.config.resize)
            feats1 = self.extractor.extract(image1, resize=self.config.resize)
            output = self.matcher({"image0": feats0, "image1": feats1})

        feats0, feats1, output = [rbd(x) for x in (feats0, feats1, output)]

        keypoints0 = feats0["keypoints"].detach().cpu().numpy()
        keypoints1 = feats1["keypoints"].detach().cpu().numpy()
        matches = output["matches"].detach().cpu().numpy()
        scores = output.get("scores")
        scores_np = None if scores is None else scores.detach().cpu().numpy()

        return build_correspondence_set(
            provider_name="cvg/LightGlue",
            extractor_name=self.config.extractor,
            reference_image_size=(ref_w, ref_h),
            after_image_size=(aft_w, aft_h),
            reference_keypoints=keypoints0,
            after_keypoints=keypoints1,
            match_indices=matches,
            scores=scores_np,
            provider_metadata={
                "max_num_keypoints": self.config.max_num_keypoints,
                "filter_threshold": self.config.filter_threshold,
                "depth_confidence": self.config.depth_confidence,
                "width_confidence": self.config.width_confidence,
                "resize": self.config.resize,
                "device": self.device,
                "mixed_precision": self.config.mixed_precision,
            },
        )
