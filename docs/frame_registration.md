# Frame Registration v0.3a

Frame registration answers a narrow question before geometry comparison:

> Are BEFORE and AFTER still in the same global image coordinate system?

It is not allowed to normalize away local architectural deformation.

## Current baseline

The current module accepts already-established point correspondences and uses RANSAC to estimate a global similarity transform.

Reported values:
- scale;
- rotation;
- translation X/Y;
- translation magnitude;
- correspondence count;
- inlier count and fraction;
- median inlier residual.

## Important trust boundary

The module does **not** warp AFTER.

It only measures the technical correction implied by the correspondences and decides whether that correction is inside configured limits.

Default limits are intentionally conservative:
- translation: 20 px;
- scale delta: 2%;
- rotation: 0.5°;
- minimum inlier fraction: 60%.

These are development defaults, not production thresholds.

## Why similarity instead of free homography

A free local or projective warp can hide the very deformation Geometry Guardian is intended to detect.

A restricted global model is easier to audit:
- global crop/translation can be reported;
- small resize can be reported;
- unexpected rotation or larger scale change becomes REVIEW_REQUIRED;
- weak correspondence support becomes INSUFFICIENT_DATA.

## Next feature provider

The planned feature-provider path is:

```text
BEFORE / AFTER
  ↓
SuperPoint
  ↓
LightGlue
  ↓
point correspondences
  ↓
RANSAC frame registration
  ↓
report-only transform + trust status
```

LightGlue will be an evidence provider, not the authority on geometry preservation.
