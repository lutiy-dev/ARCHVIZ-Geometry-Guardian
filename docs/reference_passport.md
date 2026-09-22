# Reference Passport v0.1

The Reference Passport is the stable description of what Geometry Guardian knows about the BEFORE image.

## Design requirements

1. It must be valid without a 3D scene.
2. Scene Truth is optional enrichment.
3. Provenance is stored per property.
4. Conflicting evidence is preserved.
5. Passport validity is separate from check capability.
6. Reference completeness is separate from AFTER comparison coverage.

## Minimum passport

A minimum passport needs:
- unique passport ID;
- reference image ID;
- image dimensions;
- zero or more reference elements;
- capabilities;
- limitations.

A passport with no windows can still be valid. It simply cannot perform opening-level geometry checks.

## Element identity

Stable IDs must survive detector changes and display sampling.

Examples:
- `F01` facade
- `W017` window/opening
- `D002` door
- `B004` balcony

## Property provenance

Each substantial property may have its own source and verification state.

Recommended sources:
- `human_annotation`
- `image_measurement`
- `scene_object`
- `scene_projection`
- `render_pass`
- `detector:<name>`
- `derived:<algorithm>`

Verification values:
- `verified`
- `human_verified`
- `partially_verified`
- `unverified`
- `conflict`

## Scene Truth rule

Scene data does not overwrite image evidence silently.

When scene projection and human-visible image outline disagree:
- keep both;
- record the conflict;
- choose the appropriate property for the specific check;
- do not upgrade comparison confidence merely because a scene exists.

## Capabilities

Initial capability vocabulary:
- `frame_check`
- `silhouette_check`
- `facade_line_check`
- `opening_geometry_check`

States:
- `available`
- `limited`
- `unavailable`

## Coverage terminology

**Reference completeness**: how much of the intended reference is known/prepared.

**Comparison coverage**: how much of that reference was actually verified against AFTER.

Example:

```text
Reference completeness:
40 / 40 openings geometry-ready

Comparison coverage:
28 / 40 verified on AFTER

Unverified:
5 occluded
4 too small
3 ambiguous
```
