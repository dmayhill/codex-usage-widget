# v1.0.0 Release, Version Label, and Repository Cleanup

## Summary

Prepare the current `codex/reliability-fixes` worktree for one GitHub release PR:

- Set the app version to Semantic Versioning `1.0.0`.
- Display `v 1.0.0` in small muted text immediately left of the close button.
- Record that the Store-based human visual walkthrough passed.
- Keep the separate non-Store Codex test explicitly skipped and non-required.
- Reduce root clutter without restructuring the application.
- Create an umbrella GitHub issue, open and review one PR, merge it, tag `v1.0.0`, and publish a GitHub release with the Windows executable.

## Implementation Changes

### Version and UI

- Set `pyproject.toml` version to `1.0.0`.
- Add a runtime `APP_VERSION = "1.0.0"` constant in the existing application module.
- Add a test that ensures the runtime version and project metadata remain synchronized.
- Add a header label displaying exactly `v 1.0.0`.
- Position it immediately left of the existing `x` close button.
- Use the existing muted color, a small scaled Segoe UI font, and responsive positioning so it does not overlap or clip at the minimum sidebar scale.
- Do not add executable file-version metadata or a new packaging subsystem; the visible app version is the requested release feature.

### Root cleanup

The intended root inventory will be:

```text
.gitignore
LICENSE
README.md
codex_usage_widget.py
pyproject.toml
start-codex-usage-widget.vbs
.github/
docs/
scripts/
tests/
```

- Move operational PowerShell and debug/reset command launchers into `scripts/`.
- Keep the VBS launcher at root as the primary double-click entry point.
- Update the VBS launcher, script path resolution, installer output, README, architecture documentation, and handoff documentation for the new locations.
- Correct stale launcher references, including the installer’s current reference to a nonexistent `start-codex-usage-widget.cmd`.
- Archive, rather than delete, the existing review notes and local remediation ticket records under `docs/archive/`.
- Remove only generated artifacts such as build output, distribution output, generated PyInstaller spec files, runtime state, caches, and temporary test artifacts.
- Expand repository ignores for generated cache/temp/runtime files.
- Leave inaccessible pre-existing directories untouched if Windows file locks prevent safe removal; report those exact paths rather than forcing deletion.

### Documentation and acceptance state

Update the README and continuity documents to:

- Identify the project as version `1.0.0`.
- Document the new version label.
- Reflect the cleaned launcher layout.
- Record the successful Store-based human visual walkthrough.
- Remove the human walkthrough from deferred work.
- Record the non-Store Codex variant as intentionally skipped and not a release gate.
- Document the official release and executable distribution workflow.
- Preserve the existing limitation that the widget depends on authenticated Codex state and `codex-cli-usage`.

## Verification Plan

Run locally:

- `python -m pytest -q`
- `python -m compileall -q codex_usage_widget.py tests`
- `git diff --check`
- Version synchronization test.
- Launcher/path reference checks.
- Root inventory and generated-artifact checks.
- Pinned Windows packaging build.
- Verify `dist\CodexUsageWidget.exe` is non-empty.
- Run a focused packaged visual check confirming:
  - `v 1.0.0` is visible and subdued.
  - The label is left of the close button.
  - It remains readable at the current narrow/sidebar scale.
  - It does not interfere with dragging, refreshing, or closing.
- Treat the already-passed Store Codex walkthrough as the supported-environment acceptance evidence; do not install or validate another Codex distribution.

## GitHub and Release Workflow

1. Perform a read-only GitHub/authentication preflight.
   - If the stale `127.0.0.1:9` proxy remains active, correct the task-scoped proxy environment before retrying.
   - Do not repeat remote commands unchanged if connectivity remains unavailable.

2. Create one umbrella GitHub issue covering:
   - v1.0.0 versioning.
   - UI version label.
   - root cleanup.
   - documentation synchronization.
   - release packaging.

3. Commit the current remediation plus this release work in logical commits on `codex/reliability-fixes`.

4. Push the branch and open one PR targeting `main`, linked to the umbrella issue.

5. Run a formal standards/spec review of the complete PR diff and address only in-scope findings.

6. Wait for the Windows validation workflow and resolve any failures caused by this work.

7. Review the final PR diff and checks. Submit an approval if GitHub permits approval by the current account. If GitHub rejects self-approval, do not bypass that restriction; report the PR as reviewed and ready for another authorized reviewer.

8. Merge the PR after required checks/review are satisfied.

9. From the merged commit:
   - Build the pinned standalone executable.
   - Create tag `v1.0.0`.
   - Publish the GitHub release.
   - Attach `CodexUsageWidget.exe`.
   - Include concise release notes covering the reliability fixes, version label, Store validation, and supported installation path.

## Assumptions

- `1.0.0` is the correct release version.
- Semantic Versioning 2.0.0 is the intended versioning protocol.
- One PR is preferred over splitting the existing remediation and release cleanup.
- Review artifacts should remain recoverable but should not clutter the project root.
- Generated binaries remain out of Git and are attached only to the GitHub release.
- No unrelated refactoring, package-layout migration, or non-Store Codex installation will be added.
