# 08 — Documentation and Repository Hygiene Update

**What to build:** Reconcile user and project documentation with the final runtime, installer, diagnostics, and validation behavior.

**Blocked by:** 01 — Percent Semantics Contract; 02 — Responsive Usage Refresh and CLI Discovery; 03 — Single-Instance Widget Lock; 04 — State Validation and Bounded Diagnostics; 05 — Title-First Store Focus Detection; 06 — Pinned, Non-Executing Installer Bootstrap.

**Status:** complete — implemented locally

- [x] Documentation distinguishes source-run state storage from packaged `%LOCALAPPDATA%` storage.
- [x] Installer prerequisites and missing-`uv` behavior are accurate.
- [x] Diagnostics and validation status are documented.
- [x] Runtime logs are ignored by Git.
- [x] Stale statements claiming no test suite or missing scripts are removed.
