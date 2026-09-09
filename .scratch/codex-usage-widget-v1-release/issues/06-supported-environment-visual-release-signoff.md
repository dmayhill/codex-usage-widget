# 06 - Complete Supported-Environment Visual Release Sign-off

**What to build:** The packaged widget receives a focused supported-environment walkthrough confirming that the new version label integrates cleanly with the existing Store Codex workflow and interactions.

**Blocked by:** 05 - Run Integrated Regression and Packaging Validation.

**Status:** complete — supported manual validation passed

- [x] The packaged widget shows `v 1.0.0` in subdued text immediately left of the close button.
- [x] The label is readable at the supported narrow/sidebar scale and does not overlap or clip.
- [x] Existing drag, refresh, focus visibility, and close interactions remain usable based on the user-reported manual pass; the thread explicitly itemizes drag, focus, and close, while refresh was not separately listed.
- [x] The supported Microsoft Store Codex walkthrough is recorded as passed after the version-label change.
- [x] No separate non-Store Codex installation or validation is required.

**Evidence:** The user reported that manual tests passed. The #06 thread records the version label, drag, focus visibility, close interaction, and Store Codex hide/unhide behavior as passing. No code changes were required.
