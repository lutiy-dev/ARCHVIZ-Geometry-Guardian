# LAB Research — MiniMax H3 / RTX 3070 8 GB

**Date:** 2026-11-09  
**Status:** LAB / DOCUMENTED, NOT TESTED  
**Scope:** external node-pack research for geometry-preserving architectural video generation. This is **not** a dependency, model recommendation validated by runtime, or Production Standard for Geometry Guardian.

## Motivation

Explore controlled Corona-render-to-video experiments with MiniMax H3 on an 8 GB NVIDIA RTX 3070. Geometry Guardian (image-based architecture QC) remains independent of MiniMax H3 and should not be coupled to video-generation custom nodes.

## Candidate A — MiniMax H3 LongMedia

- Upstream: https://github.com/vizart-vj/ComfyUI-MiniMax-H3-LongMedia
- Documentation inspected: upstream README_RU.md, docs/SAMPLER_OPTIMIZATION_RU.md, docs/ARCHITECTURE_RU.md, docs/MODES_GUIDE_RU.md, pyproject.toml.
- **Documented release/version:** 0.6.63 in inspected files; not a runtime compatibility assertion.
- Intended functions: H3 conditioning (`t2va`, `fl2va`, `ref2va`, `hybrid`, `video_ref_edit`), single/segmented/multiclip timeline, Director, TAKE caching, selective clip regeneration, integrated refine.
- Memory controls: `sampler_mode=auto`, `memory_mode=auto`, `attention_mode=auto`; optional `low_vram` / `ultra_low_vram`; Dynamic VRAM should remain enabled. The guide warns **not** to use `--disable-dynamic-vram`.
- Author-provided starting guidance for **8 GB**: short 4–6 second segments, expect transfer-bound execution. This is an upstream suggestion, **not our measured throughput**.
- Supports documented compatibility paths for stock H3, selected native INT8/W4A8 weights and FastH3/VSA. Specific checkpoint/backend combinations require separate verification.
- Risks: offload and CPU↔GPU transfer costs, activation memory pressure, Windows host RAM/disk paging, dependency/version conflicts, temporal stitching/identity drift, retained TAKE/cache artifacts, automatic selection of unknown attention path.
- Implementation recommendation: evaluate **after** a small, baseline native H3 video generation PASS; do not add Director, multiclip, refine or upscale during the baseline.

## Candidate B — MiniMax H3 Prompt Rewriter for ComfyUI

- Upstream: https://github.com/pytraveler/MiniMax-H3-Prompt-Rewriter-ComfyUI
- Documentation inspected: upstream README.md, README_RU.md, requirements.txt.
- Purpose: prompt authoring, validation, reducing, and references. **It does not accelerate H3 video diffusion**.
- Available routes documented by author: 27B LoRA writer, 8B vision rewriter, Omni rewriter, lightweight GGUF Writer, Prompt Presets.
- The author's approximate VRAM claims: 27B LoRA GGUF ~13 GB minimum, 8B vision GGUF ~9 GB, Omni ~9 GB, lightweight GGUF Writer ~5 GB. Approximate figures are NOT independently benchmarked here.
- Preferred 8 GB experiment: **Writer GGUF** (or presets without loading a model), with prompt-check before video generation. The 27B / 8B / Omni LoRA alternatives are not a sensible first-step baseline on this card.
- Listed requirements include Python packages `transformers>=4.57.1`, `peft>=0.17`, `accelerate>=1.10`, `bitsandbytes>=0.43` (non-Darwin), `aiohttp`, `av`, etc. Installing may alter current ComfyUI Python dependencies; verify first.
- Potential caveats: model downloads, llama.cpp binaries and separate CUDA runtime, dependency conflicts, GPU memory contention when a writer remains loaded.

## Geometry Guardian separation

The **Corona/3ds Max render is geometry truth**. H3 may animate the shot but does not become a geometry source of truth. No prompt can guarantee geometry retention.

Minimal QC targets for each H3 output:
- window/door positions and proportions;
- facade silhouette / roof / cornices;
- camera movement consistency and unintended building deformation;
- consistency across frames, flicker, temporal artifacts;
- record comparison coverage and uncertain regions rather than reporting unconditional PASS.

Geometry Guardian current v0.2 QC is image-based, and a per-frame video QC integration is **NOT IMPLEMENTED**. Do not mark a video PASS solely because a text prompt mentions preservation.

## Proposed one-variable-at-a-time LAB plan (not run)

1. Preflight ComfyUI version, installed H3 nodes, model filenames and formats, Python/PyTorch/CUDA, available system RAM, Windows pagefile and free disk space.
2. Baseline short native H3 image-to-video generation with **one input Corona frame**, no LongMedia and no rewriter. Candidate starting target **608×352, ~4 seconds**; these are proposed test settings, not validated optimum.
3. Observe CUDA allocated/reserved VRAM, RAM peak, paging, first failing node, wall-clock time and generated image quality.
4. On baseline PASS: test LongMedia `auto/auto/auto` on the *same input, seed, checkpoint, resolution and duration*, changing only the execution wrapper.
5. On stable generation PASS: compare Prompt Writer GGUF to manually crafted prompts, without changing generation parameters; unload writer before video sampling.
6. Only after reproducible PASS: evaluate segmented generation and selective rerender, then optional refine separately.

**PASS:** completed video generation without OOM; runtime and peak resource use recorded; credible visual geometry retention on chosen reference regions with clear coverage; reproducible short run.  
**FAIL / STOP:** CUDA OOM or repeated crash, unbounded paging, missing model/node/backend, severe geometry distortion, uncontrolled camera drift or missing observable output. Stop and inspect before modifying additional variables.

## Evidence status

- **CONFIRMED by upstream files:** feature names, documented memory modes, author guidance, and dependencies listed above.
- **INFERRED:** applicability to our controlled Corona → H3 → QC workflow.
- **NOT CONFIRMED:** installed environment, actual RTX 3070 performance, RAM requirements on this specific machine, local checkpoint compatibility, output quality and integration with Geometry Guardian.
- **TESTED:** none on the user's hardware.
- **Production:** NOT APPROVED.

## Sources

- https://github.com/vizart-vj/ComfyUI-MiniMax-H3-LongMedia/blob/main/README_RU.md
- https://github.com/vizart-vj/ComfyUI-MiniMax-H3-LongMedia/blob/main/docs/SAMPLER_OPTIMIZATION_RU.md
- https://github.com/vizart-vj/ComfyUI-MiniMax-H3-LongMedia/blob/main/docs/ARCHITECTURE_RU.md
- https://github.com/pytraveler/MiniMax-H3-Prompt-Rewriter-ComfyUI/blob/main/README_RU.md
- https://github.com/pytraveler/MiniMax-H3-Prompt-Rewriter-ComfyUI/blob/main/requirements.txt
