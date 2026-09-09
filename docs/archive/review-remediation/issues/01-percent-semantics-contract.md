# 01 — Percent Semantics Contract

**What to build:** Correct remaining-usage percentage parsing so utilization fields, explicit fraction fields, and malformed values are interpreted consistently.

**Blocked by:** None — can start immediately.

**Status:** complete — implemented locally

- [x] A utilization value of `1` is treated as 1%, not 100%.
- [x] Explicit fraction values are converted correctly.
- [x] Malformed values remain unavailable rather than displaying misleading percentages.
- [x] Regression tests pass.
