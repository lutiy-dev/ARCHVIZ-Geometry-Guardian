# Validation Protocol

Geometry Guardian is developed by phase gates. A new subsystem is not trusted because it runs; it is trusted only after controlled tests.

## Phase 0 — Pure data / schema

Purpose: prove Reference Passport semantics.

Required:
- unique stable IDs;
- valid without Scene Truth;
- property-level provenance;
- capabilities/limitations;
- reference completeness;
- conflict preservation.

Exit gate:
- deterministic unit tests pass;
- no image detector required.

## Phase 1 — Deterministic geometry primitives

Purpose: verify simple measurable geometry signals.

Channels:
- local opening bbox matcher;
- contour distance;
- LSD structural lines;
- coverage/status logic.

Synthetic cases:
- identity;
- translation;
- resize;
- opening moved;
- opening widened;
- opening removed;
- opening added;
- facade line bent/broken;
- partial occlusion.

Exit gate:
- expected signal direction on all synthetic controls;
- no forced matches;
- identical input yields zero/near-zero geometric drift;
- insufficient evidence abstains.

## Phase 2 — Appearance invariance

Purpose: test false positives when geometry is unchanged.

Cases:
- exposure ±;
- contrast/gamma change;
- day → night;
- warm/cool white balance;
- stone color/material change;
- glazing/reflection change;
- mild sharpening/blur;
- AI relighting without intended geometry change.

Metrics:
- false CHANGE_CANDIDATE rate;
- REVIEW_REQUIRED rate;
- comparison coverage;
- per-channel failure reasons.

Exit gate:
- thresholds frozen on development subset before evaluation subset.

## Phase 3 — Frame stability

Purpose: detect technical image-coordinate changes without hiding architectural deformation.

Cases:
- exact identity;
- small X/Y translation;
- crop;
- uniform scale;
- aspect-ratio stretch;
- slight rotation;
- camera/perspective change;
- repeated-window false correspondences;
- correspondences clustered in one image region.

Rules:
- transform is always reported;
- AFTER is not silently warped;
- weak registration blocks or downgrades downstream verdicts.

Exit gate:
- known technical transforms measured within tolerance;
- camera/perspective changes do not produce false global CLEAR.

## Phase 4 — Feature provider benchmark

Candidates:
- SuperPoint + LightGlue;
- LoFTR or another dense matcher if justified later.

Feature providers output a unified correspondence format.

Benchmark dimensions:
- day/day;
- day/night;
- material change;
- reflections;
- repetitive facade;
- sparse facade;
- occlusion;
- small distant structure.

Metrics:
- match count;
- inlier count/fraction;
- spatial coverage;
- median residual;
- repeatability;
- wrong-neighbor rate on repeating facades;
- runtime.

No winner is selected before benchmark.

## Phase 5 — Detector adapters

Candidates:
- SAM3;
- GroundingDINO;
- Florence-2;
- YOLO-World / other open-vocabulary detector.

Detectors are candidate providers only.

Benchmark:
- GT manually verified openings;
- precision / recall;
- duplicate FP;
- small-window recall;
- pair stability BEFORE/AFTER;
- runtime;
- truncation behavior.

Exit gate:
- detector failure cannot directly become geometry failure.

## Phase 6 — Visibility / occlusion

Purpose: distinguish "not visible enough" from "changed".

Cases:
- vegetation;
- people;
- signage;
- bloom/glare;
- deep shadow;
- blown highlights;
- motion blur / AI smearing.

Exit gate:
- occluded/uncertain elements become INSUFFICIENT_DATA or REVIEW_REQUIRED;
- no forced missing verdict.

## Phase 7 — Scene Truth optional branch

Purpose: enrich reference when reliable scene data exists.

Validate:
- scene version;
- camera;
- frame;
- output resolution;
- crop/render region;
- post-render edits when known.

Exit gate:
- unverified/conflicting scene data never upgrades confidence;
- property-level provenance preserved.

## Phase 8 — Real archviz benchmark

Dataset should include:
- multiple projects;
- multiple facade styles;
- near and distant views;
- day/night;
- low and high AI denoise;
- appearance-only edits;
- known synthetic geometry edits;
- natural AI geometry failures.

Primary metrics:
- true geometry-change detection;
- false alarms from appearance;
- comparison coverage;
- ambiguous/unverified fraction;
- wrong-neighbor match rate;
- human verification time.

## Phase 9 — ComfyUI integration

Only after core behavior is stable:
- Reference Setup node;
- Architecture Compare node;
- QC Inspector cards;
- QC Export;
- display sampler.

UI must not change core calculations.

## Release rule

A module status moves through:

`DESIGNED → IMPLEMENTED → UNIT_TESTED → BENCHMARKED → PRODUCTION_CANDIDATE → PRODUCTION_STANDARD`

"CI green" means code/tests run successfully. It does **not** mean the algorithm is production-validated.
