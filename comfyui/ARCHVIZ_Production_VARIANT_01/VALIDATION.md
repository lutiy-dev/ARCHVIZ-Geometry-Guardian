# ARCHVIZ Production · VARIANT 01 — Validation

Status: **LAB / TESTED OFFLINE**

## Preserved generation baseline
- `RealVisXL_V4.0.safetensors`
- `diffusers_xl_canny_full.safetensors`
- `RealESRGAN_x4plus.safetensors` / Lanczos

No silent model substitution was made.

## Offline self-test
```text
SELF_TEST: PASS
workflow_nodes=41 links=62
prepared_media_inputs=0
lazy_switches=4
state_repeat_same_original=PASS
localpass_skip=PASS
```

Validated:
- importable workflow JSON structure;
- unique node/link IDs;
- no PREPARED LoadImage media-input dependency;
- 4 AUTO mask contracts;
- 4 PREPARED mask contracts;
- 4 lazy AUTO/PREPARED source switches;
- repeated STATE ENTRY with the same ORIGINAL;
- SKIP pass without generator execution.

## Installer simulation
**PASS**

Validated:
- old archviz_production_backup* moved outside custom_nodes;
- active custom node installed cleanly;
- workflow installed to user/default/workflows;
- deterministic demo inputs generated/copied to LAB/shared input;
- generation models and Python packages are not modified.

## Runtime boundary
Final GPU/runtime acceptance requires the target ARCHVIZ_LAB workstation, its installed ComfyUI nodes and local model files.
