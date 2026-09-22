# Benchmark Region Ground Truth v0.3e

The wrong-neighbor metric requires semantic region identity.

A feature matcher only returns point pairs. It does not know whether a point belongs to window W017 or W018.

For benchmark data we therefore allow optional human-verified polygons with stable IDs on both images.

## Principle

```text
Reference polygons: W001, W002, ...
AFTER polygons:     W001, W002, ...
         ↓
feature correspondences
         ↓
point-in-polygon assignment
         ↓
reference_region_id / after_region_id
         ↓
wrong-neighbor metric
```

## Why polygons instead of detector boxes

Benchmark ground truth must not depend on the detector being evaluated.

The first benchmark pack should therefore use manually checked polygons or rectangles.

## Ambiguous overlaps

If one point falls inside more than one GT polygon, Geometry Guardian does **not** guess the region identity. That match becomes non-evaluable for semantic wrong-neighbor scoring.

## Important

Region GT is benchmark metadata only. It is not required for normal Geometry Guardian operation.

Its purpose is to answer a development question:

> Is a feature provider numerically matching the image while semantically jumping between repeated architectural elements?

## First real dataset recommendation

For the initial repetitive-facade pair, annotate at least 10–20 visible windows with the same stable IDs in BEFORE and AFTER.

This gives us the first meaningful wrong-neighbor measurement on actual archviz imagery.
