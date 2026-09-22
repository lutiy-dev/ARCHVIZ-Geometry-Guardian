# GT Preview v0.3j

Status: **IMPLEMENTED**

Region ground truth must be visually audited before the benchmark is frozen.

Geometry Guardian can now render labeled overlays for both BEFORE and AFTER.

## Command

```bash
python scripts/preview_region_gt.py \
  benchmarks/ARCHVIZ_QC_PACK_001/gt/repetitive_dev.json \
  --reference benchmarks/ARCHVIZ_QC_PACK_001/images/repeating_before.png \
  --after benchmarks/ARCHVIZ_QC_PACK_001/images/repeating_after.png \
  --output-dir benchmarks/ARCHVIZ_QC_PACK_001/gt/previews/dev
```

Outputs:

```text
reference_gt_preview.png
after_gt_preview.png
```

Each semantic region is outlined and labeled with its stable ID such as:

```text
W001
W002
...
```

## Why this gate exists

A JSON/CSV file can be syntactically valid while still containing:
- W017 placed on the wrong window;
- swapped neighboring IDs;
- a rectangle shifted outside the visible opening;
- different semantic ordering between BEFORE and AFTER.

Those mistakes are especially dangerous because they can make the wrong-neighbor benchmark accuse the matcher when the ground truth itself is wrong.

## Rule before dataset freeze

For every repetitive-facade GT pair:

1. build JSON from the CSV table;
2. pass coordinate validation;
3. render BEFORE and AFTER previews;
4. visually verify IDs side-by-side;
5. only then include the GT in the frozen dataset lock.

The preview is a human-audit aid only. It does not modify benchmark GT.
