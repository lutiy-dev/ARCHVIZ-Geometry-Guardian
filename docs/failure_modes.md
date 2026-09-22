# Failure Modes / Risk Map

This document defines known ways Geometry Guardian can be wrong before further implementation expands the system.

The goal is not to eliminate uncertainty by force. The goal is to **detect when the system should abstain**.

## 1. Reference-side failures

### 1.1 Wrong reference image
The passport was built from a different render/version/crop than the BEFORE image being checked.

**Risk:** every downstream measurement can be precise but irrelevant.

**Required mitigation:**
- reference image fingerprint / dimensions;
- explicit passport_id;
- scene-reference validation when scene data exists;
- fail closed on unresolved mismatch.

### 1.2 Incomplete reference annotation
Only part of the facade/openings are known.

**Risk:** false impression of full-pass QC.

**Required mitigation:**
- reference completeness reported separately from comparison coverage;
- capability flags;
- no global CLEAR without sufficient intended-area coverage.

### 1.3 Human annotation error
A manually confirmed opening/line is incorrectly drawn or assigned.

**Risk:** stable but wrong ground reference.

**Required mitigation:**
- provenance and verification state per property;
- editable annotations;
- optional second-review workflow for production reference passports.

### 1.4 Scene Truth mismatch
Scene version/camera/crop differs from BEFORE.

**Risk:** authoritative-looking but wrong projections.

**Required mitigation:**
- scene branch is optional;
- Scene Reference Validation gate;
- conflict does not overwrite image evidence;
- unverified scene data never upgrades confidence.

---

## 2. Frame / registration failures

### 2.1 Pure technical translation
The whole image is shifted/cropped without architectural change.

**Risk:** false geometry alarms.

**Response:** report technical shift and allow only within configured bounds.

### 2.2 Resize / aspect-ratio change
AFTER is globally rescaled or stretched.

**Risk:** element size changes look architectural.

**Response:**
- uniform scale may be measured as technical correction;
- anisotropic stretch is not silently corrected;
- aspect-ratio mismatch -> REVIEW_REQUIRED or preprocessing requirement.

### 2.3 Camera change
Perspective/camera moved.

**Risk:** almost all facade geometry appears changed.

**Response:** frame gate should stop element-level verdicts or downgrade them to NOT_VERIFIED.

### 2.4 Repetitive-facade correspondence aliasing
Feature matcher pairs one window/corner with a neighboring repeated element.

**Risk:** false registration and false local confirmation.

**Response:**
- minimum spatial spread of correspondences;
- ambiguity diagnostics;
- local identity constraints;
- RANSAC is evidence, not authority;
- repeated-pattern stress tests mandatory.

### 2.5 Correspondences concentrated in one small region
Global registration appears numerically stable but has no frame-wide support.

**Risk:** local patch defines the whole transform.

**Response:** future registration quality must include spatial coverage, not only inlier fraction.

---

## 3. Contour evidence failures

### 3.1 Shadow edge
Lighting change creates/removes a strong edge.

**Risk:** false geometry change.

### 3.2 Reflection / glazing edge
Glass/reflection pattern changes.

**Risk:** false window-border evidence.

### 3.3 Material seam / texture edge
Stone joints, cladding, brick, noise create extra contours.

**Risk:** nearest-edge matcher jumps to material detail.

### 3.4 Low contrast / overexposure
True architectural edge disappears.

**Risk:** apparent missing geometry.

### 3.5 Anti-aliasing / sharpening
Edge location or thickness changes by a few pixels.

**Risk:** small false displacement.

**Required mitigation across contour channel:**
- ROI/local expected search;
- orientation-aware matching where possible;
- symmetric distances;
- robust percentile metrics;
- never let contour channel alone prove deletion/addition;
- visibility/evidence-quality state.

---

## 4. Line evidence failures

### 4.1 Fragmentation
One architectural line becomes many short segments.

### 4.2 Merging
Several neighboring lines become one long segment.

### 4.3 Perspective
Same facade family has sloped, converging lines.

### 4.4 Occlusion
Vegetation/person/sign breaks a structural line.

### 4.5 Decorative linear texture
Facade seams compete with structural lines.

**Required mitigation:**
- line grouping/merging stage before production use;
- local search;
- angle + position + overlap/length constraints;
- per-facade interpretation;
- no naive same-Y floor grouping.

---

## 5. Opening / element matching failures

### 5.1 Neighbor jump
W017 gets matched to W018.

**Risk:** missing opening hidden by incorrect pairing.

**Response:** expected-position local search + ambiguity + neighbor consistency as evidence only.

### 5.2 Detector miss
No candidate proposed although opening still exists.

**Risk:** false deletion.

**Response:** no candidate != confirmed removal.

### 5.3 Detector duplicate
One real opening produces multiple candidates.

**Risk:** false ambiguity/addition.

**Response:** duplicate handling belongs to detector adapter; QC preserves ambiguity if unresolved.

### 5.4 Partial occlusion
Window is partly hidden by vegetation, person, sign, bloom, flare.

**Response:** INSUFFICIENT_DATA / NOT_VERIFIED, not deletion.

### 5.5 Real intentional redesign
Architecture was intentionally modified.

**Response:** exclusion/allowed-change policy in Reference Passport.

### 5.6 Tiny distant elements
Opening exists but resolution is insufficient.

**Response:** capability may exist while comparison status remains INSUFFICIENT_DATA.

---

## 6. Evidence-fusion failures

### 6.1 Correlated channels counted as independent
Canny contour and LSD line may both arise from the same pixel edge.

**Risk:** false confidence through double voting.

**Response:** channels have dependency groups; fusion must not assume statistical independence.

### 6.2 One noisy channel dominates
A detector emits many observations and overwhelms other evidence.

**Response:** one channel = one vote class; repeated measurements do not multiply authority.

### 6.3 Threshold overfitting
Thresholds tuned on one facade work badly elsewhere.

**Response:** development set / frozen test set separation.

### 6.4 CLEAR under low coverage
Only easy visible elements are verified.

**Response:** global CLEAR requires minimum comparison coverage and no critical unverified regions.

---

## 7. Scene Truth failures

### 7.1 Correct scene, wrong render state
Objects, modifiers, animation frame, render region, proxy state differ.

### 7.2 Geometry vs visible appearance mismatch
Scene opening geometry differs from visible frame/glass/reveal contour.

### 7.3 Post-retouch after rendering
BEFORE was edited in Photoshop.

### 7.4 Render displacement/procedural effects
Visible contour differs from base mesh.

**Response:** property-level provenance; preserve image and scene evidence separately.

---

## 8. Output / UX failures

### 8.1 Green overlay implies full verification
Display sample hides unchecked areas.

**Response:** sampler/display never changes decision; coverage always visible.

### 8.2 "Missing" wording presented as fact
Algorithm only failed to match.

**Response:** use "missing candidate", "unmatched reference", or CHANGE_CANDIDATE until confirmed.

### 8.3 Ambiguity hidden
Best candidate accepted despite nearly equal second-best candidate.

**Response:** ambiguity margin required.

### 8.4 Technical correction hidden
Registration corrected the image silently.

**Response:** all registration transforms must be reported numerically.

---

## 9. Production principle

When evidence is weak or contradictory, Geometry Guardian should prefer:

`REVIEW_REQUIRED` or `INSUFFICIENT_DATA`

over a confident but unsupported CLEAR / CHANGE_CANDIDATE.
