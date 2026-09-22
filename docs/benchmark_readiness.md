# Benchmark Readiness Gate v0.3g

The next stage of Geometry Guardian needs real archviz images, but a random folder of pairs is not a valid benchmark.

Before any provider thresholds are tuned, the pack must pass a readiness gate.

## Hard errors

The checker blocks READY when:
- a required case category is missing;
- dev/eval split is incomplete;
- a case has no `::dev` or `::eval` suffix;
- an image is missing or unreadable;
- `geometry_change` is not explicitly marked as expected change;
- preservation controls are not explicitly marked as no geometry change;
- repetitive-facade cases have no semantic region GT;
- repetitive GT has fewer than 10 common stable IDs;
- region GT is malformed or contains duplicate IDs.

## Warnings

The checker currently warns on:
- same image file reused across dev/eval;
- unexpected aspect-ratio mismatch outside the technical-transform category.

Warnings do not necessarily invalidate a pack, but they must be reviewed before freeze.

## Why this matters

This gate prevents us from tuning a matcher against an accidentally incomplete benchmark.

It also makes the first real ALIKED + LightGlue run interpretable: if a case fails, we know the test definition itself passed basic quality checks.

## Development state

`READY` means only that the dataset structure is suitable for benchmarking.

It does not mean:
- the provider is good;
- thresholds are calibrated;
- Geometry Guardian is production-ready.
