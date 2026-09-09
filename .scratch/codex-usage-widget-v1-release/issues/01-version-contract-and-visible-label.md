# 01 - Add v1.0.0 Version Contract and Visible Version Label

**What to build:** The widget identifies itself as version `1.0.0` using Semantic Versioning and displays subdued `v 1.0.0` text immediately to the left of the close button.

**Blocked by:** None - can start immediately.

**Status:** complete — implemented locally

- [x] The project metadata and runtime version are both `1.0.0`.
- [x] The widget displays exactly `v 1.0.0` in a small, muted, scaled label left of the close button.
- [x] The label remains positioned with the close-button clearance and scaling logic in place; narrow-scale visual confirmation remains part of ticket 06.
- [x] Automated coverage verifies the version contract and label value; 38 tests passed.
