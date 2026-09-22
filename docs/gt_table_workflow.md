# Region GT Table Workflow v0.3i

Status: **IMPLEMENTED**

Semantic window IDs can now be prepared in a spreadsheet-friendly CSV instead of hand-writing JSON polygons.

## 1. Create a table

```bash
python scripts/create_gt_table.py \
  benchmarks/ARCHVIZ_QC_PACK_001/gt/repetitive_dev.csv \
  --count 20 \
  --prefix W
```

The file contains:

```text
region_id,
ref_x1, ref_y1, ref_x2, ref_y2,
aft_x1, aft_y1, aft_x2, aft_y2,
notes
```

IDs are pre-created as:

```text
W001 ... W020
```

The CSV can be edited in Excel, Google Sheets, LibreOffice, or a text editor.

## 2. Enter rectangles

For every stable opening, enter the bounding rectangle in BEFORE and AFTER.

Coordinates are image pixels.

A row may omit one side when an element is intentionally unavailable there, but repetitive-facade wrong-neighbor benchmarking requires enough IDs visible on **both** sides.

## 3. Build validated JSON GT

```bash
python scripts/build_region_gt.py \
  benchmarks/ARCHVIZ_QC_PACK_001/gt/repetitive_dev.csv \
  --reference benchmarks/ARCHVIZ_QC_PACK_001/images/repeating_before.png \
  --after benchmarks/ARCHVIZ_QC_PACK_001/images/repeating_after.png \
  --output benchmarks/ARCHVIZ_QC_PACK_001/gt/repetitive_dev.json
```

The build fails if:
- IDs are duplicated;
- a rectangle is incomplete;
- x2 <= x1 or y2 <= y1;
- annotation points are outside the image;
- images cannot be decoded;
- fewer than the configured number of stable IDs exist on both sides.

## Why rectangles first

For the first provider benchmark we need semantic identity more than pixel-perfect segmentation.

Rectangles are:
- faster to audit;
- easier to type/correct;
- sufficient for point-to-window identity scoring;
- independent of the detector under test.

Polygon editing can be added later when a benchmark actually needs tighter visible outlines.

## Trust rule

The GT table is human benchmark metadata. It must not be populated automatically from the same feature provider whose wrong-neighbor behavior is being measured.
