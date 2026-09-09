# 04 — State Validation and Bounded Diagnostics

**What to build:** Safely reject invalid saved geometry and provide bounded local diagnostics without recording usage data or secrets.

**Blocked by:** None — can start immediately.

**Status:** complete — implemented locally

- [x] Invalid scale and malformed geometry fall back safely.
- [x] Diagnostics are stored under the user-local application state directory.
- [x] Logs rotate at 256 KB with one backup.
- [x] Logs contain only timestamps, exception types, and relevant paths.
- [x] State and logging behavior are tested.
