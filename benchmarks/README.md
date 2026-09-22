# Benchmark data

Real project images are intentionally **not** stored in the repository by default.

Recommended local layout:

```text
benchmarks/
  ARCHVIZ_QC_PACK_001/
    manifest.json
    benchmark_dataset.lock.json
    images/
      ...
    gt/
      ...
```

The manifest and lock can be committed if licensing/privacy permits. Project renders may remain local.

Workflow:

```text
prepare pairs
→ annotate semantic GT where needed
→ assign ::dev / ::eval IDs
→ freeze dataset
→ verify lock
→ run provider benchmark
→ tune only on ::dev
→ evaluate on ::eval
```

Use:

```bash
python scripts/freeze_benchmark_dataset.py \
  benchmarks/ARCHVIZ_QC_PACK_001/manifest.json \
  --dataset-id ARCHVIZ_QC_PACK_001 \
  --version 0.1.0 \
  --output benchmarks/ARCHVIZ_QC_PACK_001/benchmark_dataset.lock.json
```
