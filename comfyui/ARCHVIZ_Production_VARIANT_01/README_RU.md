# ARCHVIZ Production · VARIANT 01 — AUTO/PREPARED MASK ENGINE

Это первый канонический вариант production workflow после локальной эмуляции и исправления v0.2.

## Архитектура
- ORIGINAL остаётся immutable geometry reference.
- FACADE / ROAD / GREENERY / PEOPLE работают как отдельные local passes.
- Для каждого pass есть две независимые ветки масок:
  - AUTO: ORIGINAL → SAM3 → AUTO Mask Contract.
  - PREPARED: заранее подготовленные PNG → PREPARED Mask Contract.
- Mask Source Switch — lazy: невыбранная ветка не исполняется.
- Mask Preview показывает фактическую область воздействия до RUN.
- В pass маски приходят явно кабелем как AP_MASKSET.
- RUN / CACHE / SKIP, Accepted State, manual ACCEPT/REJECT, QC, Inspector и Upscale сохранены.

## Генеративный baseline не изменён
- RealVisXL_V4.0.safetensors
- diffusers_xl_canny_full.safetensors
- RealESRGAN_x4plus.safetensors / Lanczos

## Installer
Запустить:
`RUN_INSTALL_VARIANT_01.cmd`

Installer:
- выносит старые archviz_production_backup* из custom_nodes;
- устанавливает активный archviz_production;
- генерирует demo assets;
- копирует workflow в user/default/workflows;
- не меняет Python packages, Torch/CUDA или generation models.

## Первый запуск
Открыть:
`ARCHVIZ_Production_VARIANT_01.json`

Сначала INSPECT. Затем для теста одного pass:
Facade=RUN, остальные SKIP. Перед RUN проверить FACADE · EFFECT AREA PREVIEW.
