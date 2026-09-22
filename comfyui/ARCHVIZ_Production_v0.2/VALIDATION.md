# Verification — 2026-09-22

## Scope

Windows / RTX 4090, installed ARCHVIZ_LAB ComfyUI 0.36.0, frontend 1.52.7. Existing Python environment and model library; no pip install or weight download. Separate temporary ComfyUI processes, no restart of the user's running LAB.

## Passed

- **26 unit/contract tests**: original 10 acceptance tests plus state integrity, idempotent decisions, stale parent/cache rejection, exact protected pixels, restart recovery, incomplete request guard, upscale protection and native graph structure.
- **17 CPU integration checks**: exported full graph in the real executor, test-only synthetic processor, all four local passes, conservative upscale, manual accepts, cache invalidation. Synthetic substitution is confined to the test launcher, absent from installed nodes.
- **18 GPU integration checks**: actual RealVisXL SDXL + Canny ControlNet, all four local passes including masked erase for People, RealESRGAN x4plus, overlap-tiled SDXL generative upscale, manual acceptance and rejection, zero new model calls on repeated candidate/CACHE queues.
- **8 frontend checks**: actual rgthree controls for five groups; each toggle removes exactly its processor from the compiled prompt and preserves state routing. The frontend-produced graph executes. A normal Run-button click completed INSPECT and visibly reported `processor_calls=0`.

The UI check caught and fixed two serialization issues before installation: Comfy's extra seed-control widget, and the requirement for the bundled demo original to appear in LoadImage's root input list. Five masks/processor groups remain separately bypassable; state, composite and acceptance logic within each pass stay atomic.

## Evidence

`test-results.txt`, `test-results.json`, `integration-cpu.json`, `integration-gpu.json`, `integration-ui.json`. Installation reports per-file SHA-256 equality in `installation-report.json`.

GPU smoke uses a synthetic 768×512 architectural test image, 256-pixel local processing crops, two sampling steps per local pass, and one step per generative upscale tile. These are compatibility tests. Default production graph settings are 1024-pixel crops and 24 local sampling steps; no commercial-quality validation on a client render has been performed.

## Intentional limits

- No automatic semantic window matching or commercial/artistic quality certification. Geometry/Visual statuses remain NOT_EVALUATED / REVIEW_REQUIRED. Canny displacement is advisory.
- Manual masks, one RGB frame. No automatic segmentation, external API backend, SeedVR2 adapter or Scene Truth adapter in this release.
- Weight identity uses path, size and modification time; float image/state/QC payloads use SHA-256.
- New node registration in the already-running LAB requires its next ordinary restart. The installed files are verified; the active LAB process was not hot-patched or restarted.
- Browser test server's DynamicVRAM initialization was disabled with a test-process-only CLI flag for the GPU smoke launcher. No installed runtime settings were changed.
