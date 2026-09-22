# Benchmark Dataset Freeze v0.3f

A benchmark is only useful if the image pairs do not silently change while thresholds are being tuned.

Geometry Guardian therefore supports a **dataset lock file**.

## Frozen dataset rule

Once the first real benchmark pack is accepted:

1. manifest is complete;
2. development/evaluation split is fixed;
3. all files receive SHA-256 fingerprints;
4. the lock file is committed;
5. thresholds may be tuned only on the development split;
6. evaluation split remains untouched until a planned evaluation run.

## Case naming

The current split convention is deliberately explicit:

```text
identity_01::dev
identity_02::eval
night_01::dev
night_02::eval
```

The suffix is part of the case ID and makes accidental cross-split reuse visible in reports.

## Why freeze before tuning

Without a frozen benchmark pack, it is very easy to:
- replace a difficult AFTER with an easier image;
- adjust annotations after seeing provider output;
- tune thresholds on evaluation data;
- compare provider versions on slightly different image sets.

Any of those would make later performance claims unreliable.

## Lock file

The lock records:
- dataset ID;
- dataset version;
- manifest SHA-256;
- path, size, and SHA-256 for every referenced image/GT file.

If any file changes, verification fails.

## First real pack target

Recommended initial pack:

- 1 facade family;
- 9 required failure-mode categories;
- at least one `::dev` and one `::eval` case for every tuned category;
- 10–20 stable window IDs on the repetitive-facade subset;
- known geometry edits documented before running providers.

The first pack should be small enough to inspect manually and strict enough to expose mistakes.
