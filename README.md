# ARCHVIZ Geometry Guardian

**Architecture-preservation QC for AI-assisted architectural visualization.**

Status: **v0.1 foundation / LAB**

Geometry Guardian checks whether architecture visible in an input reference is preserved after AI processing while allowing non-geometric changes such as lighting, materials, season, people, vegetation, and sky.

## Core principle

The mandatory pipeline is image-based:

```text
BEFORE
  ↓
Reference Setup
  ↓
Base Reference Passport
  ↓
Architecture Compare
  ↓
QC Inspector / Export
```

Scene data is **optional enrichment**, never a required foundation:

```text
3ds Max / Corona / passes
  ↓
Scene Truth Adapter
  ↓
Scene Reference Validation
  ↓
optional property-level enrichment
  ↓
Reference Passport
```

Scene Truth can strengthen knowledge about the reference, but it does **not** prove that geometry is preserved in a flat AFTER image.

## Two independent confidence axes

1. **Reference confidence** — how well we know what the reference geometry should be.
2. **Comparison confidence** — how well the AFTER image supports a preservation/change conclusion.

A window can be scene-confirmed in the reference and still be `NOT_VERIFIED` in AFTER because of occlusion, glare, low resolution, or ambiguity.

## QC statuses

- `CLEAR` — no geometric change detected in the verified area.
- `CHANGE_CANDIDATE` — evidence indicates possible geometric change.
- `REVIEW_REQUIRED` — correspondence/evidence is ambiguous.
- `INSUFFICIENT_DATA` — the target cannot be checked reliably.

Every result must report **comparison coverage**. A green global status is not allowed when coverage is insufficient.

## Reference Passport

The passport stores stable IDs and property-level provenance for:
- facade regions;
- silhouette / roof / major corners;
- structural lines;
- windows / doors / balconies;
- exclusions and ignore regions;
- uncertain regions;
- optional Scene Truth enrichment;
- capabilities and limitations.

Example element:

```yaml
id: W017
identity:
  value: W017
  source: scene_object
  verification: verified
reference_outline:
  value: [[100,100],[160,100],[160,220],[100,220]]
  source: image_annotation
  verification: human_verified
expected_projection:
  value: [100,100,160,220]
  source: scene_projection
  registration: verified
after_match:
  status: ambiguous
```

## v0.1 development target

First prototype:
- one facade;
- fixed camera;
- 10–20 human-verified openings;
- synthetic known changes;
- no detector dependency required.

Control cases:
1. unchanged;
2. light/exposure only;
3. material/color only;
4. one opening moved;
5. one opening removed;
6. one opening added;
7. one opening resized;
8. facade edge warped;
9. partial occlusion.

## Repository layout

```text
src/geometry_guardian/
  reference/
  registration/
  geometry/
  matching/
  evidence/
  qc/
  adapters/
schemas/
tests/
docs/
examples/
```

## Roadmap

**v0.1** Reference Passport + deterministic local opening matcher + synthetic tests  
**v0.2** contour and line evidence (OpenCV LSD / distance fields)  
**v0.3** frame registration evidence (SuperPoint/LightGlue/RANSAC)  
**v0.4** optional detector adapters (SAM3 / GroundingDINO / Florence-2 / YOLO-World)  
**v0.5** ComfyUI adapter + Inspector cards  
**v1.0** validated production QC protocol
