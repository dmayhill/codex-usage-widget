# Project State

_Snapshot: 2026-09-08. Based on the current worktree, repository history through `b6d2e2d`, and the checked-in documentation/configuration._

## Purpose

The Codex Usage Widget is a small Windows always-on-top widget that displays Codex-style remaining usage for the 5-hour and weekly windows, reset information, plan, and refresh time while Codex is in focus.

## Status and maturity

Early but usable utility, version `0.1.0`. The main feature path, Windows launchers, reliability fixes from tickets 01–07, automated validation, and Windows CI configuration are implemented. The current worktree is intentionally dirty with those changes plus the documentation/repository-hygiene work; preserve unrelated existing changes when continuing.

## Completed

- Tkinter widget with always-on-top, borderless dark-panel presentation.
- 5-hour and weekly usage display, reset formatting, plan display, and refresh status.
- Automatic refresh every five minutes, with one retry after transient usage-tool failures.
- Visibility tied to Codex focus, including a window-title fallback for Store-style Codex windows in the current worktree.
- Dragged-position persistence, monitor work-area clamping, last-known-good geometry, scaling for narrow sidebars, and reset/recenter support.
- Quiet `.vbs` launcher, visible debug launchers, Python-runtime candidate fallback, duplicate-process cleanup, and standalone PyInstaller build script.
- Focused tests for usage parsing, state persistence/migration, bounded diagnostics, focus detection, refresh behavior, and launcher/packaging assumptions.
- Windows push/PR validation workflow covering tests, Python compilation, and a non-publishing standalone-package smoke check.

## Work in progress

- Ticket 09 installed/packaged smoke validation is complete at the native window-state level. A separate live
  non-Store Codex variant was explicitly skipped because the supported environment uses the Microsoft Store build.
- Release ownership and the preferred distribution artifact remain undefined.

## Remaining work and known limitations

- The widget depends on Codex login state and the external `codex-cli-usage` tool; it does not call a documented Codex usage endpoint directly.
- Usage JSON normalization is heuristic because it accepts several possible field names/shapes.
- Tkinter, Windows APIs, monitor behavior, and launcher/runtime selection are platform-specific.
- A packaged executable was built and exercised locally: duplicate launch, `%LOCALAPPDATA%` position persistence,
  close during a slow refresh, Store Codex focus visibility, unrelated-window hiding, failure diagnostics, and missing-`uv`
  guidance passed. This native window-state evidence is not a substitute for a human visual walkthrough.
- There is no formal release artifact, versioning workflow, or publishing workflow. Packaging is a local/CI smoke check only.

## Validation and release

The repository contains configuration for Python `>=3.10`, Ruff line length, and PyInstaller packaging through the pinned `uvx`/`uv tool run` path. `python -m pytest -q` runs the focused automated suite, and `python -m compileall -q codex_usage_widget.py tests` checks Python compilation. The Windows workflow in `.github/workflows/windows-validation.yml` runs those checks on pushes and pull requests, then builds and verifies a non-empty `dist/CodexUsageWidget.exe` using Python 3.12, `pytest==8.4.1`, `uv==0.11.17`, and the shared PyInstaller pin. The target machine still needs Codex authentication and a working usage-data source.

## Operational Validation

- Automated tests: verified locally on 2026-09-08; 36 focused tests passed.
- Python compilation: verified locally on 2026-09-08 with `python -m compileall -q codex_usage_widget.py tests`.
- Packaged executable: built locally with pinned PyInstaller `6.21.0`; non-empty output measured at 12,732,616 bytes.
- Packaged native smoke: duplicate launch, position restore, close during refresh, Store Codex visibility, unrelated
  focus hiding, bounded diagnostics, and missing-`uv` guidance passed.
- Normal title-based Codex focus: verified by focused tests; the separate live non-Store Codex GUI variant was intentionally
  skipped and is not required for the current supported environment.
- Representative live Codex usage payload and external authentication: unverified; the failure smoke used isolated local
  paths and a ticket-local slow command.
- Human visual walkthrough and release/distribution acceptance: deferred; native window-state checks do not replace it.

## Priorities

1. Perform the deferred human visual walkthrough on the supported Microsoft Store Codex environment.
2. Establish release ownership and the preferred distribution artifact.
3. Keep the README, continuity docs, and CI workflow synchronized when runtime or packaging behavior changes.
