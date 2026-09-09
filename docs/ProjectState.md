# Project State

_Snapshot: 2026-09-09. Based on the current working tree, repository history through `925a97f`, and the repository configuration._

## Purpose

The Codex Usage Widget is a small Windows always-on-top widget that displays Codex-style remaining usage for the 5-hour and weekly windows, reset information, plan, and refresh time while Codex is in focus.

## Status and maturity

Usable v1.0.0 utility. The main feature path, visible version label, cleaned Windows launcher layout, reliability fixes,
automated validation configuration, and Windows CI configuration are implemented locally through ticket 04. The current
worktree is intentionally dirty with those changes plus later release-ticket files; preserve unrelated existing changes
when continuing.

## Completed

- Tkinter widget with always-on-top, borderless dark-panel presentation.
- 5-hour and weekly usage display, reset formatting, plan display, and refresh status.
- Automatic refresh every five minutes, with one retry after transient usage-tool failures.
- Visibility tied to Codex focus, including a window-title fallback for Store-style Codex windows in the current worktree.
- Dragged-position persistence, monitor work-area clamping, last-known-good geometry, scaling for narrow sidebars, and reset/recenter support.
- Quiet `.vbs` launcher, visible debug launchers, Python-runtime candidate fallback, duplicate-process cleanup, and standalone PyInstaller build script.
- v1.0.0 runtime metadata and the subdued `v 1.0.0` label immediately left of the close button.
- Cleaned repository layout with the root `.vbs` entry point and operational PowerShell/CMD helpers under `scripts/`.
- Focused tests for usage parsing, state persistence/migration, bounded diagnostics, focus detection, refresh behavior, and launcher/packaging assumptions.
- Windows push/PR validation workflow covering tests, Python compilation, and a non-publishing standalone-package smoke check.
- Documentation synchronized with the v1.0.0 launcher, packaging, and release-acceptance state.

## Work in progress

- The supported Microsoft Store Codex human visual walkthrough passed with no issues noted. The separate non-Store Codex
  installation and validation is intentionally skipped because it is not required for the supported environment and is not
  a release gate.
- Ticket 05 integrated regression and packaging validation, followed by tickets 06–09 release signoff, GitHub review/merge,
  and publication, remain to be completed.

## Remaining work and known limitations

- The widget depends on Codex login state and the external `codex-cli-usage` tool; it does not call a documented Codex usage endpoint directly.
- Usage JSON normalization is heuristic because it accepts several possible field names/shapes.
- Tkinter, Windows APIs, monitor behavior, and launcher/runtime selection are platform-specific.
- The standalone executable workflow is documented: run `scripts/install-windows.ps1`, then `scripts/build-exe.ps1`, and
  distribute the resulting `dist\CodexUsageWidget.exe`. The target machine still needs Codex login state and
  `codex-cli-usage`.
- The later integrated validation, GitHub PR, merge, tag, and publication steps have not been performed by this
  documentation-only ticket.

## Validation and release

The repository contains configuration for Python `>=3.10`, Ruff line length, and PyInstaller packaging through the pinned
`uvx`/`uv tool run` path. `python -m pytest -q` runs the focused automated suite, and
`python -m compileall -q codex_usage_widget.py tests` checks Python compilation. The Windows workflow in
`.github/workflows/windows-validation.yml` runs those checks on pushes and pull requests, then builds and verifies a
non-empty `dist/CodexUsageWidget.exe` using Python 3.12, `pytest==8.4.1`, `uv==0.11.17`, and the shared PyInstaller pin.
The workflow does not publish the executable. The target machine still needs Codex authentication and a working
usage-data source.

## Operational Validation

- Supported Microsoft Store Codex human visual walkthrough: passed with no issues noted.
- Separate non-Store Codex installation and validation: intentionally skipped; it is not required for the supported
  environment and is not a release gate.
- Documentation/reference checks for ticket 04: performed locally; no application behavior or archived review evidence was
  changed.
- Integrated regression, packaging-build, and publication checks: not run by this documentation-only ticket; ticket 05 and
  later tickets own those checks.

## Priorities

1. Run integrated regression and packaging validation for the v1.0.0 work.
2. Complete the remaining supported-environment release signoff and GitHub release workflow.
3. Keep the README, continuity docs, and CI workflow synchronized when runtime or packaging behavior changes.
