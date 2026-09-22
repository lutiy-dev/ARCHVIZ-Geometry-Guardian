# Feature Provider Benchmark Protocol v0.3c

The provider adapter can run and CI can be green while the matching strategy is still unsuitable for architectural QC.

Therefore feature providers are benchmarked independently from the rest of Geometry Guardian.

## Required case families

Each provider should be tested on paired images from these groups:

1. same render / identity;
2. exposure and white-balance change;
3. material / facade-color change;
4. day → night;
5. reflections / glazing change;
6. repetitive window grid;
7. sparse facade;
8. strong vegetation occlusion;
9. distant small architecture;
10. technical crop/translation/scale;
11. camera mismatch;
12. known local geometry edit.

## Metrics per case

Record:
- extracted keypoint count for each image;
- accepted match count;
- score median/min/max;
- grid spatial coverage;
- point-cloud bbox coverage;
- duplicate feature fraction;
- RANSAC inlier count/fraction;
- median inlier residual;
- reported global transform;
- region-evaluable matches;
- wrong-neighbor match count/fraction;
- runtime;
- peak VRAM if available.

## Wrong-neighbor metric

Repeated architecture is a critical failure mode.

When benchmark ground truth assigns both ends of a match to known region IDs:

```text
wrong_neighbor_fraction =
  matches(reference_region_id != after_region_id)
  / region_evaluable_matches
```

A provider may have:
- excellent RANSAC residual;
- high inlier fraction;
- good spatial coverage;

and still have a bad wrong-neighbor rate.

This metric is therefore reported separately and must not be hidden inside a generic "confidence" score.

## Development / evaluation split

Do not tune thresholds on all available pairs.

Recommended process:
- development subset: tune provider and gate parameters;
- freeze parameters;
- evaluation subset: report results unchanged.

## Provider comparison

No overall winner is selected before real data exists.

Providers should be compared by failure mode, for example:
- strongest day/night stability;
- lowest wrong-neighbor rate;
- best sparse-facade coverage;
- lowest runtime/VRAM.

A provider can remain useful for one evidence role even if another provider wins a different category.

## Current implementation status

Implemented:
- neutral CorrespondenceSet;
- spatial/duplicate quality gate;
- RANSAC registration;
- optional LightGlue adapter;
- benchmark result structure;
- wrong-neighbor metric.

Not yet benchmarked:
- ALIKED + LightGlue on real archviz pairs;
- any LoFTR implementation;
- runtime/VRAM on target RTX 4090 environment.
