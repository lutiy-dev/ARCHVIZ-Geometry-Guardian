# Controlled Variant Registry v0.3k

Status: **IMPLEMENTED**

Each real BEFORE/AFTER benchmark pair must now declare what was intentionally changed and what must remain invariant.

This prevents a dangerous benchmark ambiguity:

> "The night image looks different, but do we actually know geometry was preserved while creating it?"

## Core fields

Every controlled pair records:
- variant ID;
- category;
- reference image;
- AFTER image;
- geometry expectation;
- intentionally changed properties;
- invariant properties;
- human-readable change description;
- creation method;
- optional known changed element IDs;
- optional exclusion regions.

## Geometry expectation

Allowed values:

```text
preserved
changed
unknown
```

Examples:
- day/night → `preserved`
- material-only → `preserved`
- occlusion-only → `preserved`
- known shifted opening → `changed`
- camera mismatch → usually `unknown`

## Architecture invariants

For preservation controls, the registry should explicitly retain:

```text
camera_pose
projection
building_silhouette
facade_grid
major_openings
```

A missing invariant produces a warning rather than silently assuming it.

## Known geometry edits

A `geometry_change` case must explicitly declare geometry as an intended changed property.

Prefer also recording stable IDs:

```json
"known_changed_element_ids": ["W017"]
```

This lets later QC evaluation ask not only:

> Did the system detect a change?

but:

> Did it localize the known change to W017?

## Camera mismatch

Camera mismatch is intentionally different.

The source 3D geometry can be unchanged while the 2D projection changes everywhere. Therefore this category should not be treated as an ordinary geometry-preservation pair.

Its role is to test whether the frame gate blocks misleading downstream QC.

## Validation

Use:

```bash
python scripts/check_variant_registry.py examples/controlled_variants.example.json
```

The validator rejects semantic contradictions such as:
- appearance-only pair declaring geometry as intentionally changed;
- geometry-change pair without geometry in changed_properties;
- camera-mismatch pair without camera change declaration;
- identity pair declaring non-zero intended changes.

## Trust principle

The registry records **how the pair was created**, not what Geometry Guardian later concludes.

Benchmark truth must remain independent from the algorithm under evaluation.
