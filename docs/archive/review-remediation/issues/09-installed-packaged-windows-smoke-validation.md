# 09 — Installed/Packaged Windows Smoke Validation and Review Closure

**What to build:** Perform the focused Windows walkthrough that demonstrates the remediation as a complete user outcome.

**Blocked by:** 01 — Percent Semantics Contract; 02 — Responsive Usage Refresh and CLI Discovery; 03 — Single-Instance Widget Lock; 04 — State Validation and Bounded Diagnostics; 05 — Title-First Store Focus Detection; 06 — Pinned, Non-Executing Installer Bootstrap; 07 — Windows Continuous Validation; 08 — Documentation and Repository Hygiene Update.

**Status:** validated locally on 2026-09-08; separate non-Store variant intentionally skipped

- [x] Duplicate launch produces only one widget. Two packaged launch attempts produced one `TkTopLevel` widget
  window; the second launch exited with code 0.
- [x] Packaged position persistence works after restart. A real packaged window moved to `(123,177)`, saved that
  position on close, and restored it after restart under `%LOCALAPPDATA%\CodexUsageWidget`.
- [x] Closing during refresh produces no traceback. A slow ticket-local usage command kept refresh active while the
  real packaged window received `WM_CLOSE`; the executable exited and no traceback-bearing diagnostic was written.
- [x] Normal and Store Codex focus visibility works at the available evidence levels. Normal title matching and
  inaccessible-path behavior pass the focused tests. The live installed Store Codex window kept the widget visible;
  an existing unrelated Notepad window hid it; restoring Store Codex showed it again. The separate live non-Store
  Codex variant was intentionally skipped because it is not required for the supported environment.
- [x] Failure diagnostics are usable and bounded. The packaged failure path wrote a 212-byte local diagnostic with
  the exception type and state path, omitting the exception message and usage payload; rotation is covered by tests.
- [x] Missing-`uv` guidance is clear. Installer and packaging scripts exited before install/build, printing the
  official installation URL and `winget install --id=astral-sh.uv -e` guidance.
- [x] Review findings are marked addressed or explicitly deferred below.

## Validation evidence

- `python -m pytest -q`: 36 passed.
- `python -m compileall -q codex_usage_widget.py tests`: passed.
- `scripts/build-exe.ps1` with pinned PyInstaller `6.21.0`: produced a non-empty 12,732,616-byte executable.
- The packaged smoke runs used isolated paths under `temp\validation\ticket09-20260908-1515`.

## Review closure

Addressed by tickets 01–08 and verified here: packaged state persistence, close-safe refresh callbacks, single-instance
locking, bounded diagnostics, title-first/Store focus fallback, pinned non-executing installer guidance, Windows CI and
packaging checks, and synchronized documentation/repository hygiene.

Explicitly deferred: a human visual walkthrough. The separate live non-Store Codex packaging variant was intentionally
skipped and is not a release gate for the supported Microsoft Store environment. The available native window-state
evidence and automated normal-title tests do not replace the human release-gate walkthrough. Low-priority
review suggestions such as event-driven focus hooks, layout-constant cleanup, and broader distribution hardening remain
out of scope for this ticket.
