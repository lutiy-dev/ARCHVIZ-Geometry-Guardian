# LightGlue Feature Provider Adapter

Status: **IMPLEMENTED — runtime benchmark pending**

Geometry Guardian now has an optional adapter for the official `cvg/LightGlue` implementation.

The adapter is deliberately outside the QC core.

```text
NumPy RGB images
  ↓
LightGlueProvider
  ↓
local feature extractor
  ↓
LightGlue matcher
  ↓
CorrespondenceSet
  ↓
provider quality gate
  ↓
RANSAC frame registration
```

## Default extractor: ALIKED

The adapter defaults to **ALIKED + LightGlue**, not SuperPoint.

Reason: the official LightGlue repository states that:
- LightGlue code and pretrained weights are Apache-2.0;
- ALIKED was published under BSD-3-Clause;
- SuperPoint's pretrained implementation/weights use a more restrictive license.

Because Geometry Guardian is intended for commercial archviz workflows, SuperPoint is blocked by default in the adapter and requires an explicit opt-in flag.

This is a project safety rule, not a legal opinion. License suitability still has to be confirmed for the intended distribution/use case.

## Supported extractor names

- `aliked` — default;
- `disk`;
- `sift`;
- `superpoint` — explicit restricted-license opt-in required.

No extractor is declared the benchmark winner yet.

## Runtime isolation

Torch and `lightglue` are imported only when `LightGlueProvider` is instantiated.

That means:
- the pure QC core remains lightweight;
- CI can test contracts without downloading neural weights;
- ComfyUI integration can later use its own compatible environment;
- a feature-provider failure does not prevent passport/report logic from loading.

## Current configuration

Development defaults:
- max keypoints: 2048;
- LightGlue filter threshold: 0.1;
- depth confidence: 0.95;
- width confidence: 0.99;
- resize: disabled by Geometry Guardian unless explicitly configured.

These are upstream-compatible starting values, not production thresholds.

## Runtime validation still required

Before this provider becomes BENCHMARKED, test:

1. unchanged render;
2. exposure/material-only change;
3. day → night;
4. repetitive windows;
5. vegetation occlusion;
6. sparse facade;
7. large flat facade;
8. intentionally moved opening;
9. camera mismatch.

Record:
- extracted keypoint counts;
- accepted match count;
- score distribution;
- spatial coverage;
- RANSAC inlier fraction;
- residual;
- wrong-neighbor rate where GT IDs exist;
- runtime and VRAM.

## Important

A good LightGlue match does not prove geometry preservation.

It only contributes frame/correspondence evidence. Local architectural QC remains a separate decision path.
