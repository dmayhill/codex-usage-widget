# Project State

_Snapshot: 2026-07-12. Based on the current worktree, repository history through `cc8ad44`, and the checked-in documentation/configuration._

## Purpose

Provide a small Windows always-on-top widget that displays Codex-style remaining usage for the 5-hour and weekly windows, reset information, plan, and refresh time while Codex is in focus.

## Status and maturity

Early but usable utility, version `0.1.0`. The main feature path and Windows launchers are implemented. The current worktree is dirty: `codex_usage_widget.py` and `start-codex-usage-widget.ps1` contain uncommitted changes related to Microsoft Store Codex focus detection and Tcl/Tk environment cleanup; `codex_usage_widget_runtime.log` is also untracked.

## Completed

- Tkinter widget with always-on-top, borderless dark-panel presentation.
- 5-hour and weekly usage display, reset formatting, plan display, and refresh status.
- Automatic refresh every five minutes, with one retry after transient usage-tool failures.
- Visibility tied to Codex focus, including a window-title fallback for Store-style Codex windows in the current worktree.
- Dragged-position persistence, monitor work-area clamping, last-known-good geometry, scaling for narrow sidebars, and reset/recenter support.
- Quiet `.vbs` launcher, visible debug launchers, Python-runtime candidate fallback, duplicate-process cleanup, and standalone PyInstaller build script.

## Work in progress

- The current uncommitted focus-detection fallback and launcher environment cleanup need runtime validation on the target Windows/Codex installations.
- The runtime log is untracked; determine whether it is diagnostic output that should remain ignored or be removed before release.

## Remaining work and known limitations

- No automated test suite is present in the repository; behavior is primarily validated by manual Windows execution.
- The widget depends on Codex login state and the external `codex-cli-usage` tool; it does not call a documented Codex usage endpoint directly.
- Usage JSON normalization is heuristic because it accepts several possible field names/shapes.
- Tkinter, Windows APIs, monitor behavior, and launcher/runtime selection are platform-specific.
- README installation text should be checked against the actual launcher filenames and current scripts before a release.
- No formal release artifact, versioning workflow, or CI configuration is present.

## Validation and release

The repository contains configuration for Python `>=3.10`, Ruff line length, and PyInstaller packaging through `uvx`. No test command or CI workflow was found. Packaging is available through `scripts/build-exe.ps1`, producing `dist/CodexUsageWidget.exe`; the target machine still needs Codex authentication and a working usage-data source.

## Priorities

1. Manually validate the current uncommitted changes on supported Windows/Codex variants.
2. Reconcile README instructions with the actual launcher set and installation behavior.
3. Decide whether to add focused tests for JSON normalization and geometry/state handling without requiring a GUI.
4. Establish a small release/validation checklist before distributing the executable.
