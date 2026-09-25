# ARCHVIZ Production · VARIANT 02 — HANSEN-STYLE SEQUENTIAL

Variant 02 сохраняет один проект без ручного Project ID и перестраивает runtime по логике Paul Hansen: выбранные этапы выполняются последовательно в одном рабочем проходе, а ручной review-gate остаётся один — в конце всей цепочки.

## Core architecture
- Один workflow-файл = один внутренний namespace.
- Workspace изолируется автоматически: `workflow namespace + ORIGINAL image hash`.
- ORIGINAL остаётся immutable source of truth.
- Рабочая цепочка:
  `ACCEPTED INPUT → FACADE → ROAD → GREENERY → PEOPLE → UPSCALE → FINAL CANDIDATE`.
- Любой stage может быть `RUN` или `SKIP`.
- `SKIP` = passthrough.
- `RUN` меняет working image и передаёт реальный результат следующему этапу.
- После полного EXECUTE создаётся один `AWAITING_ACCEPT` candidate.
- ACCEPT / REJECT выполняется один раз по итоговому результату.

## Sequential masks
Каждый AUTO mask строится от текущего working image соответствующего этапа.

Для экономии VRAM:
`CURRENT STAGE FULL IMAGE → CPU MASK REFERENCE max-side 1024 → SAM3 → mask restore to full resolution → AP Mask Contract → LocalPass`.

Полноразмерный production image не уменьшается. Уменьшается только semantic reference для SAM3.

AUTO semantics:
- RUN + AUTO + empty → `SKIPPED_EMPTY_MASK / NO_TARGET_DETECTED`; генератор не вызывается.
- RUN + PREPARED + empty → strict error.
- SKIP → passthrough; SAM3 не запускается.

## VRAM barriers
Перед SDXL/ESRGAN и после тяжёлого generation pass выполняется best-effort offload inactive models.
Это нужно, чтобы предыдущий SAM3/SDXL не занимал VRAM следующего этапа, особенно на 8 GB GPU.

## Final QC
В workflow встроен `Image Comparer (rgthree)`:
- A = ORIGINAL
- B = итоговый pipeline result
- comparer mode = Slide

Compare-ноду больше не нужно добавлять вручную.

## Generation baseline preserved
Настройки генерации не менялись:
- `RealVisXL_V4.0.safetensors`
- `diffusers_xl_canny_full.safetensors`
- Facade: 24 steps / CFG 5 / denoise 0.24 / Canny 0.65
- Road: 24 / CFG 5 / denoise 0.28 / Canny 0.55
- Greenery: 24 / CFG 5 / denoise 0.40 / Canny 0.25
- People: 24 / CFG 5 / denoise 0.85 / Canny 0.00
- Upscale: 2x; RealESRGAN_x4plus or Lanczos; generative 16 / CFG 4 / denoise 0.12 / tile 768 / overlap 128 / blend 0.5

## Validation gates
Self-test проверяет:
- Python syntax;
- workflow JSON;
- отсутствие manual Project ID;
- automatic workspace;
- true sequential stage-image topology;
- 1024px SAM3 mask-reference;
- full-resolution mask restore contract;
- link symmetry;
- встроенный FINAL COMPARE;
- комбинации F / R / G / F+R / F+G / R+G / F+R+G / F+G+Upscale / Full chain;
- generation baseline;
- installer simulation.

Статусы:
- GENERATED — код/JSON создан.
- VALIDATED — CI/self-test прошли.
- TESTED — реальный GPU runtime подтверждён на целевой машине.
