# Decision Semantics

## Core statuses

### CLEAR
No geometry change was detected **inside the verified comparison coverage**.

CLEAR never means:
- the entire image is proven identical;
- hidden 3D geometry is preserved;
- unchecked elements are safe.

### CHANGE_CANDIDATE
Evidence supports a possible geometric change that requires confirmation or exceeds configured geometry tolerances.

This is not automatically equivalent to "confirmed architectural error".

### REVIEW_REQUIRED
Evidence is contradictory, ambiguous, technically shifted, or correspondence identity is uncertain.

### INSUFFICIENT_DATA
The system does not have enough usable evidence to make a reliable comparison.

### NOT_VERIFIED
Element/reference exists in the passport, but no comparison conclusion was established for AFTER.

## Three completeness concepts

### Reference completeness
How much intended reference architecture has been prepared/known.

### Comparison coverage
How much reference architecture was actually checked in AFTER.

### Evidence quality
How strong/useful the observations are for the checked area.

These values must never be collapsed into one "confidence percentage".

## Critical-region rule

Future passports may mark critical regions/elements.

A facade/global CLEAR is blocked when:
- comparison coverage is below threshold; or
- any critical element is NOT_VERIFIED / INSUFFICIENT_DATA; or
- unresolved CHANGE_CANDIDATE exists.

## Wording policy

Prefer:
- "unmatched reference element";
- "possible missing opening";
- "change candidate";
- "not verified due to occlusion";
- "registration not confirmed".

Avoid presenting inference as fact:
- "window deleted";
- "new window added";
- "geometry preserved 100%".
