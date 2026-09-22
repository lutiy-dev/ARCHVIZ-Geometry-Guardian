# ARCHVIZ_QC_PACK_001 template

Replace the placeholder paths in `manifest.json` with real benchmark images.

## Minimum readiness gate

Before freezing the dataset:

```bash
python scripts/check_benchmark_readiness.py \
  examples/benchmark_pack_template/manifest.json
```

The checker verifies:
- all required categories exist;
- every case belongs to `::dev` or `::eval`;
- evaluation covers development categories;
- referenced images exist and can be decoded;
- preservation/change semantics are explicit;
- repetitive-facade cases include semantic region GT;
- repetitive GT has at least 10 common stable region IDs;
- obvious cross-split image reuse is reported;
- unexpected aspect-ratio mismatch is reported.

## Freeze only after READY

When readiness returns no errors:

```bash
python scripts/freeze_benchmark_dataset.py manifest.json \
  --dataset-id ARCHVIZ_QC_PACK_001 \
  --version 0.1.0 \
  --output benchmark_dataset.lock.json
```

Do not tune provider thresholds before the pack is frozen.
