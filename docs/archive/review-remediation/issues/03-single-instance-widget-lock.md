# 03 — Single-Instance Widget Lock

**What to build:** Prevent duplicate widget processes regardless of whether the app is started through a launcher or directly.

**Blocked by:** None — can start immediately.

**Status:** complete — implemented locally

- [x] The first instance acquires a Windows named mutex.
- [x] A second instance exits quietly with code 0.
- [x] No second widget window or state-write race is created.
- [x] The mutex is released after normal and failed startup paths.
