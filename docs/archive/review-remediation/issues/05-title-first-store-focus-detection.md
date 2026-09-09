# 05 — Title-First Store Focus Detection

**What to build:** Make Store/Codex focus detection resilient to inaccessible process paths and future package-name changes.

**Blocked by:** None — can start immediately.

**Status:** complete — implemented locally

- [x] Constrained Codex title matching is evaluated first.
- [x] The package marker remains only as a fallback.
- [x] Inaccessible process paths do not raise.
- [x] Unrelated windows are rejected.
- [x] Normal and Store focus cases are covered by tests.
