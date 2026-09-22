# Final Benchmark Pack Audit v0.3l

Status: **IMPLEMENTED**

This is the last preparation gate before a real provider run.

## One-command audit

```bash
python scripts/audit_benchmark_pack.py \
  benchmarks/ARCHVIZ_QC_PACK_001/manifest.json \
  --variants benchmarks/ARCHVIZ_QC_PACK_001/controlled_variants.json \
  --lock benchmarks/ARCHVIZ_QC_PACK_001/benchmark_dataset.lock.json \
  --json-output benchmarks/ARCHVIZ_QC_PACK_001/audit.json
```

Expected result:

```text
READY | frozen=True | errors=0
```

If any hard error exists, the provider benchmark should not run.

## What the audit combines

The final audit checks:
- benchmark readiness;
- required categories;
- dev/eval split;
- image existence/decoding;
- repetitive-facade GT;
- controlled variant semantics;
- one variant spec for every manifest case;
- no orphan/missing semantic cases;
- dataset freeze lock;
- checksum integrity after freeze.

## Run policy

```text
NOT READY
  ↓
fix pack
  ↓
audit again

READY
  ↓
run ALIKED + LightGlue benchmark
```

The audit does not evaluate provider quality. It only guarantees that the test pack is internally consistent enough to interpret results.

## First real test

Once the first pack reports READY:

```bash
python scripts/run_lightglue_benchmark.py \
  benchmarks/ARCHVIZ_QC_PACK_001/manifest.json \
  --output benchmarks/ARCHVIZ_QC_PACK_001/results_aliked_lightglue.json
```

Default provider:

```text
ALIKED → LightGlue → CorrespondenceSet → quality gate → RANSAC
```

That is the first real runtime milestone.
