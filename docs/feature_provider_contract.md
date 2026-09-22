# Feature Provider Contract v0.3b

Geometry Guardian must not depend on one feature matcher.

SuperPoint+LightGlue, LoFTR, or future providers must export the same neutral correspondence format.

## Provider output

A provider returns:

- provider name/version;
- reference image size;
- AFTER image size;
- list of point correspondences;
- optional score per pair;
- optional stable feature IDs;
- optional facade/region IDs;
- provider metadata.

The QC core receives no provider-specific tensors.

## Why this boundary exists

A feature matcher can fail in several ways:
- too few matches;
- repeated-window neighbor aliasing;
- matches concentrated in one small facade patch;
- duplicate feature usage;
- strong numerical RANSAC result from weak spatial support.

Therefore RANSAC is not called directly on arbitrary provider output.

The required path is:

```text
Feature Provider
  ↓
CorrespondenceSet
  ↓
Validation
  ↓
Spatial Coverage / Duplicate Diagnostics
  ↓
Provider Gate
  ↓
RANSAC Registration
```

## Spatial coverage

Two separate diagnostics are required:

1. **Grid coverage** — how many cells across the image contain matches.
2. **Bounding-box coverage** — how much image area is spanned by the point cloud.

This prevents a dense cluster in one corner from pretending to establish global registration.

The v0.3b defaults are development defaults:
- minimum 12 matches;
- 4×4 spatial grid;
- minimum 25% grid coverage;
- minimum 20% bounding-box coverage.

These are not production thresholds.

## Duplicate feature diagnostics

If provider feature IDs are available, reuse of the same source/target feature is measured.

Duplicate matches do not necessarily mean the provider is wrong, but they prevent automatic trust when the duplicate fraction is too high.

## Repetitive facade / wrong-neighbor problem

Stable point IDs alone do not solve semantic window identity.

Later benchmark datasets should carry ground-truth region/window IDs where possible. Then the provider benchmark can measure:

`wrong-neighbor rate = matches assigned to the wrong repeated architectural element / evaluated matches`

That metric belongs to benchmark evaluation rather than generic RANSAC.

## Provider policy

No provider is considered the winner before benchmark.

Planned comparison:
- SuperPoint + LightGlue;
- LoFTR if justified by appearance-change tests;
- additional provider only if it improves a documented failure mode.
