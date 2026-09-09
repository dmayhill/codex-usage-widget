# 06 — Pinned, Non-Executing Installer Bootstrap

**What to build:** Make installation and packaging reproducible without piping a live remote script into PowerShell execution.

**Blocked by:** None — can start immediately.

**Status:** complete — implemented locally

- [x] Missing `uv` produces official installation instructions and does not execute remote code.
- [x] `codex-cli-usage` and PyInstaller versions are exact pins selected through clean validation.
- [x] Installer and build workflows consume the same version source.
- [x] A clean install and packaging smoke check succeed without publishing artifacts.

The full installer JSON check was not run because the machine's TLS certificate is expired; no TLS bypass was used.
