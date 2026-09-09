# 02 — Responsive Usage Refresh and CLI Discovery

**What to build:** Make usage refresh responsive and reliably locate `codex-cli-usage` across standard Windows uv installations.

**Blocked by:** None — can start immediately.

**Status:** complete — implemented locally

- [x] Each CLI attempt times out after 10 seconds.
- [x] Exactly one retry remains enabled.
- [x] PATH and standard uv locations are searched deterministically.
- [x] Timeout, retry, and discovery behavior are covered by tests.
