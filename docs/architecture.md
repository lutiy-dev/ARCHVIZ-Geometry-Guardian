# Architecture v0.1

## 1. Mandatory image-based path

Geometry Guardian must remain usable when no 3D scene exists.

```text
BEFORE image
  ↓
Reference Setup
  ↓
Base Reference Passport
  ↓
Architecture Compare ← AFTER image
  ↓
Evidence + Coverage + Ambiguity
  ↓
QC Inspector / Export
```

## 2. Optional Scene Truth enrichment

```text
3ds Max / Corona / passes
  ↓
Scene Truth Adapter
  ↓
Scene Reference Validation
  ↓
property-level enrichment
  ↓
Reference Passport
```

The scene branch never replaces the image reference path.

## 3. Scene Truth trust boundary

Scene data may define reference identity, source geometry, projection, or depth only when registration to BEFORE has been verified.

Validation states:
- `verified`
- `partially_verified`
- `unverified`
- `conflict`

A scene-confirmed reference element may still be impossible to verify in AFTER.

## 4. Property-level provenance

Provenance belongs to properties, not only to whole objects. Example: identity may come from the scene while visible outline comes from a human annotation.

Conflicting evidence must be preserved, not silently overwritten.

## 5. Passport validity vs capability

A passport can be structurally valid while some checks are unavailable.

Example:
- silhouette data exists → silhouette check available;
- no opening annotations → opening geometry check unavailable.

## 6. Evidence hierarchy

Planned evidence channels:
- frame/camera registration evidence;
- silhouette/contour evidence;
- long-line/facade-grid evidence;
- local feature correspondences;
- optional detector/segmentation candidates;
- visibility/occlusion evidence.

No single channel is treated as absolute truth for AFTER.

## 7. Matching rule

Known reference elements are searched locally around an expected position. Global matching across a repetitive facade is not the default.

The matcher must be allowed to refuse a correspondence.

## 8. Output semantics

Global status is accompanied by:
- reference completeness;
- comparison coverage;
- unverified element count and reasons;
- ambiguous match count;
- change candidates.

Sampler/display selection must never change the underlying QC result.
