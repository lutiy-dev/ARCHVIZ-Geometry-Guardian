# ARCHVIZ Production · VARIANT 02 — Validation

Current target status: **VALIDATED only after GitHub Actions PASS / GPU runtime still required**

## Static / CI validation
The self-test validates:
- Python syntax;
- workflow JSON;
- manual Project ID removal;
- automatic workspace isolation;
- Hansen-style sequential working-image topology;
- stage combination contract;
- SAM3 mask-reference max-side 1024;
- full-resolution AUTO-mask restore path;
- VRAM barrier hooks;
- one final review gate;
- final rgthree Image Comparer;
- full link symmetry (origin output links ↔ target input links);
- AUTO-empty / PREPARED-empty policies;
- preserved generation baseline;
- installer simulation and installed workflow SHA-256 equality.

## Required real GPU acceptance
Static PASS is not runtime TESTED.

Minimum target-machine matrix:
1. FACADE only
2. ROAD only
3. GREENERY only
4. FACADE + ROAD
5. FACADE + GREENERY
6. ROAD + GREENERY
7. FACADE + ROAD + GREENERY
8. FACADE + GREENERY + UPSCALE
9. FACADE + ROAD + GREENERY + PEOPLE + UPSCALE

PASS requires:
- every selected RUN stage actually executes;
- each downstream stage consumes the previous stage result;
- SAM3 AUTO mask is generated on the current stage image;
- no downstream stage is suppressed by a previous RUN;
- FINAL COMPARE shows the accumulated output;
- no OOM under the target resolution/GPU profile.

Only after this matrix passes may Variant 02 be marked **TESTED**.
