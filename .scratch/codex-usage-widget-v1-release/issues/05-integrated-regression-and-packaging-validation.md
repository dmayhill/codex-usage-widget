# 05 - Run Integrated Regression and Packaging Validation

**What to build:** The completed v1.0.0 changes pass the repository’s automated, compilation, packaging, layout, and artifact checks and produce a usable standalone Windows executable.

**Blocked by:** 01 - Add v1.0.0 Version Contract and Visible Version Label; 02 - Relocate Operational Launch and Install Scripts; 03 - Archive Review Evidence and Clean Generated Artifacts; 04 - Synchronize Documentation and Release Acceptance State.

**Status:** complete — implemented locally

- [x] The focused automated test suite passes: 40 tests passed.
- [x] Python compilation checks pass.
- [x] Repository whitespace, launcher-reference, root-inventory, and Git-ignore checks pass.
- [x] The pinned Windows packaging build succeeds with PyInstaller 6.21.0.
- [x] The standalone executable exists and is non-empty at `dist\CodexUsageWidget.exe` (12,731,901 bytes); packaged launch is covered by ticket 06.
- [x] Generated validation outputs remain excluded from Git.
