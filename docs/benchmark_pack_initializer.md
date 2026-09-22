# Benchmark Pack Initializer v0.3h

Status: **IMPLEMENTED**

The repository can now create the folder structure for the first real benchmark pack from one selected facade reference.

## Command

```bash
python scripts/init_benchmark_pack.py \
  benchmarks/ARCHVIZ_QC_PACK_001 \
  --reference path/to/before.png \
  --eval-reference path/to/second_before.png \
  --dataset-id ARCHVIZ_QC_PACK_001
```

The evaluation reference is optional during initial preparation, but a valid frozen benchmark still needs an evaluation split.

## Generated structure

```text
ARCHVIZ_QC_PACK_001/
  images/
    reference_dev.*
    reference_eval.*   # when provided
  gt/
    repetitive_dev.template.json
    repetitive_eval.template.json
  manifest.json
  PACK_PLAN.md
```

The initializer creates only identity controls automatically.

It does **not** invent appearance/day-night/occlusion/geometry-change images. Those must be real controlled variants whose semantics are known.

## Why we do not auto-generate the whole benchmark

A benchmark is supposed to test reality, not the assumptions of the preparation script.

For example:
- an AI-generated night image may already contain geometry drift;
- an "occlusion" edit may accidentally alter facade pixels;
- a synthetic camera change needs to be documented;
- a removed window must be a known edit, not detector inference.

Therefore the helper scaffolds the pack and shows missing work, while readiness/freeze gates enforce discipline.

## Region GT templates

The initializer creates empty semantic GT templates for repetitive facades.

Populate them with the same stable IDs in BEFORE and AFTER:

```text
W001, W002, ... W020
```

At least 10 common IDs are required by the current readiness gate.

## Next

After adding variants:

```text
init pack
→ fill manifest
→ fill repeated-window GT
→ readiness gate
→ freeze
→ ALIKED + LightGlue runtime benchmark
```
