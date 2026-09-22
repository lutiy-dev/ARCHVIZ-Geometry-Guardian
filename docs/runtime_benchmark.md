# Runtime Benchmark Harness v0.3d

Status: **IMPLEMENTED — real archviz dataset still required**

The benchmark harness is now separate from the provider implementation.

## Why

A neural provider can pass unit tests while failing on real architectural images. The harness records reproducible per-pair measurements instead of relying on visual impressions.

## Manifest-driven benchmark

A JSON manifest defines image pairs and their case category.

Required category families:
- identity;
- appearance change;
- day/night;
- repetitive facade;
- occlusion;
- sparse facade;
- technical transform;
- camera mismatch;
- known geometry change.

The harness warns when the manifest is incomplete.

## Runtime measurements

For each pair it records:
- provider/extractor/matcher;
- elapsed inference time;
- peak CUDA memory when available;
- match count;
- score statistics;
- spatial coverage;
- duplicate-feature diagnostics;
- RANSAC inliers/residual/transform;
- wrong-neighbor metrics when region GT is available.

## Important limitation

The current real-image LightGlue adapter does not yet assign semantic facade/window region IDs automatically.

Therefore wrong-neighbor rate is currently available for:
- synthetic/annotated correspondence sets;
- future benchmark datasets with region labels.

It must not be reported as zero merely because region GT is absent.

## Example

Use `examples/benchmark_manifest.example.json` as the dataset template.

The runtime command is:

```bash
python scripts/run_lightglue_benchmark.py path/to/manifest.json --output results.json
```

ALIKED remains the default extractor.

## Next gate

The next meaningful milestone is not more architecture code. It is a **small, curated real-image benchmark pack** with known BEFORE/AFTER semantics.

Recommended first pack:
- 1 facade;
- 1 identity pair;
- 2 appearance-only variants;
- 1 day/night pair;
- 1 repetitive facade pair;
- 1 occluded pair;
- 1 technical shift pair;
- 1 camera-change pair;
- 3 known geometry edits.

That pack should be frozen before thresholds are tuned.
