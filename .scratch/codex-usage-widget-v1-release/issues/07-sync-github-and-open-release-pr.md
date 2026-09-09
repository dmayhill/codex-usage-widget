# 07 - Synchronize GitHub and Open the Release PR

**What to build:** The complete local remediation and v1.0.0 release work are synchronized to GitHub, tracked by one umbrella issue, and presented in a single PR targeting `main`.

**Blocked by:** 06 - Complete Supported-Environment Visual Release Sign-off.

**Status:** in progress — supported validation is complete; GitHub synchronization is now authorized

- [ ] A read-only GitHub authentication and connectivity preflight succeeds before remote writes.
- [ ] One umbrella GitHub issue tracks the version, UI label, cleanup, documentation, validation, and release work.
- [ ] The approved local changes are committed in logical commits without generated artifacts or unrelated files.
- [ ] The branch is pushed without force-updating history.
- [ ] One PR targeting `main` is opened and linked to the umbrella issue.
