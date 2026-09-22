# Geometry Evidence v0.2

Geometry Guardian v0.2 adds the first image-only evidence channels. They are deliberately simple, measurable baselines.

## 1. Contour evidence

Pipeline:

```text
image
  ↓
Canny
  ↓
binary edge map
  ↓
distance transform
  ↓
BEFORE→AFTER + AFTER→BEFORE contour distances
```

Reported metrics:
- median contour displacement;
- 95th percentile contour displacement;
- supported contour fraction within a pixel tolerance;
- both directed values and symmetric summary.

Why symmetric? A one-way metric can detect a missing reference edge but miss a newly added edge, or vice versa.

Important limitation: Canny also responds to shadows, reflections, material boundaries, and texture. Contour evidence is therefore a measurement channel, not an automatic geometry verdict.

## 2. Structural-line evidence

The baseline uses OpenCV LSD.

Each detected segment is normalized to a `LineSegment` with:
- endpoints;
- midpoint;
- length;
- orientation.

Known reference lines are matched only within a local search radius, with constraints on:
- angle;
- position;
- length ratio.

The matcher may refuse a pair. Near-equal candidates become `REVIEW_REQUIRED`.

DeepLSD is intentionally not part of v0.2. It can later be benchmarked behind the same `LineSegment` interface.

## 3. Evidence fusion

The first fusion layer is rule-based, not learned.

Independent channels vote with explicit weights. Multiple measurements from one channel do not create multiple votes.

Default rule:
- 2.0+ change weight → `CHANGE_CANDIDATE`;
- any weaker change or ambiguity → `REVIEW_REQUIRED`;
- 2.0+ clear weight and no conflict → `CLEAR`;
- otherwise → `INSUFFICIENT_DATA`.

The values are protocol parameters, not statistical probabilities. They must be calibrated on a development set and then frozen for benchmark evaluation.

## 4. What v0.2 does not claim

v0.2 does not yet solve:
- camera registration;
- feature matching across strong appearance changes;
- occlusion estimation from an image;
- automatic facade/window detection;
- perspective rectification;
- final production thresholds.

Those belong to later validated stages.
