# ARCHVIZ Production · VARIANT 02 — PROJECTLESS SEQUENTIAL

Variant 02 removes the manual Project ID completely.

## Core architecture
- One workflow file is one project namespace.
- The workflow contains an internal hidden namespace in `extra.archviz_workspace_id`.
- Runtime storage is isolated automatically by `workflow namespace + ORIGINAL image hash`.
- Replacing ORIGINAL never requires renaming a project field.
- `ORIGINAL_IMMUTABLE` remains only as an internal integrity guard inside an automatically isolated workspace.

## Sequential stage references
Mask generation follows the actual state chain:
`ORIGINAL → FACADE parent → ROAD parent → GREENERY parent → PEOPLE parent`.

Each stage has an `APStateImage` node exposing that stage's current parent image to SAM3 and both mask contracts.
The Mask Source Switch receives parent `AP_STATE` directly. A blocked parent, SKIP, or CACHE cannot request AUTO/PREPARED mask branches.

## Mask semantics
- RUN + AUTO + empty → `SKIPPED_EMPTY_MASK / NO_TARGET_DETECTED`; no generator call; parent passthrough.
- RUN + PREPARED + empty → strict error.
- SKIP → parent passthrough; no mask engine.
- CACHE → accepted cache reuse; no mask engine.

## Generation baseline preserved
- RealVisXL_V4.0.safetensors
- diffusers_xl_canny_full.safetensors
- Facade 24 / CFG5 / denoise 0.24 / Canny 0.65
- Road 24 / CFG5 / denoise 0.28 / Canny 0.55
- Greenery 24 / CFG5 / denoise 0.40 / Canny 0.25
- People 24 / CFG5 / denoise 0.85 / Canny 0.00
- Upscale 2x; RealESRGAN_x4plus or Lanczos; generative 16 / CFG4 / denoise 0.12 / tile 768 / overlap 128 / blend 0.5

## Install
Close ComfyUI Desktop and run `RUN_INSTALL_DESKTOP_LAB.cmd`.
The script runs the self-test first and stops before installation if validation fails.
