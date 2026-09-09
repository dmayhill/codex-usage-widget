# 02 - Relocate Operational Launch and Install Scripts

**What to build:** The repository keeps the VBS launcher as the root-level user entry point while operational PowerShell and CMD helpers live under the scripts area and continue to launch, reset, debug, install, and build the widget correctly.

**Blocked by:** None - can start immediately.

**Status:** complete — implemented locally

- [x] The root-level VBS launcher points to the relocated start helper; routing was statically verified.
- [x] Install, debug, reset, and packaging paths resolve from the relocated scripts area; focused checks and the full 40-test suite passed.
- [x] Documentation-facing launcher instructions no longer reference a nonexistent command file.
- [x] Existing quiet-launch and debug-launch selection logic is preserved by source/test verification; a separate live console walkthrough was not run.
