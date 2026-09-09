# Architecture

This document describes the Codex Usage Widget repository.

## High-level design

The application is a single Python/Tkinter process with four concerns:

1. Read usage data from `codex-cli-usage json` or a generic local fallback cache.
2. Normalize heterogeneous usage JSON into session/weekly percentages and reset labels.
3. Render and manage a Windows desktop widget, including focus visibility, scaling, persistence, and refresh scheduling.
4. Keep machine-local state and bounded diagnostics separate from source and packaged application files.

PowerShell, CMD, and VBScript files provide installation, launch, debug, reset, and packaging workflows around the Python entry point.

## Important files

- `codex_usage_widget.py`: application entry point and all widget, Windows API, usage parsing, persistence, and refresh logic.
- `scripts/start-codex-usage-widget.ps1`: stops duplicate instances, removes incompatible Tcl/Tk environment overrides, selects a Python runtime, and starts the widget from the repository root.
- `start-codex-usage-widget.vbs`: starts the PowerShell launcher hidden for normal use.
- `scripts/start-codex-usage-widget-debug.cmd`: invokes the launcher with a visible troubleshooting console.
- `scripts/reset-codex-usage-widget.ps1` and `scripts/reset-codex-usage-widget-debug.cmd`: start with `--reset-position`.
- `scripts/install-windows.ps1`: installs `uv`/`codex-cli-usage` as needed and checks JSON access.
- `scripts/build-exe.ps1`: invokes PyInstaller through `uvx`.
- `scripts/dependency-versions.ps1`: shared exact pins for `codex-cli-usage` and PyInstaller.
- `tests/test_codex_usage_widget.py` and `tests/test_packaging_scripts.py`: focused automated coverage for runtime and workflow assumptions.
- `.github/workflows/windows-validation.yml`: Windows push/PR tests, compile check, and non-publishing packaging smoke test.
- `pyproject.toml`: package metadata and Python/Ruff configuration.

## Data flow

`UsageWidget.schedule_refresh()` starts an asynchronous refresh. `find_usage_command()` first checks `PATH`, then the configured/default Windows `uv` tool locations. `load_usage()` invokes `codex-cli-usage json`, retries once after a subprocess, timeout, or JSON error, and passes decoded data to `normalize_usage()`. If the command is unavailable, it attempts the generic cache at `%USERPROFILE%\.codex\usage-limits.json`. The normalized values are applied on the Tkinter thread by `apply_usage()`; failures preserve last-known data when available.

On startup, geometry is loaded from `codex_usage_widget_state.json`. Source runs use the file beside the script. Frozen/packaged runs use `%LOCALAPPDATA%\CodexUsageWidget\codex_usage_widget_state.json` and migrate an adjacent executable-era state file when needed. Geometry is clamped to a monitor work area, restored or centered, and saved atomically with a `last_good` position. Visibility is checked every 250 ms using the foreground process path and, where needed, foreground window title. Right-click temporarily withdraws the widget for 20 seconds.

State and diagnostics use the same active application directory: source runs write `codex_usage_widget.log` beside the
script, while packaged runs write `%LOCALAPPDATA%\CodexUsageWidget\codex_usage_widget.log`. Diagnostics contain only
timestamp, phase, exception type, and relevant paths; the rotating log is capped at 256 KB with one backup and does not
copy exception messages or usage payloads.

## Key design decisions and constraints

- Standard-library Python keeps the widget lightweight; `codex-cli-usage` is an external data source rather than vendored code.
- Tkinter updates remain on the GUI thread; usage retrieval runs in a daemon worker thread.
- Windows APIs are accessed through `ctypes`; non-Windows execution has limited fallback behavior and is not the primary target.
- Geometry is persisted separately from source and ignored by Git because it is machine/user-specific.
- Packaged state belongs under per-user `%LOCALAPPDATA%`; source state remains adjacent to the script for simple local development. A legacy packaged state beside the executable is read only for migration.
- Launchers prefer `pythonw.exe` for normal use and preserve a visible debug path for diagnosing startup failures.
- The current launcher clears `TCL_LIBRARY` and `TK_LIBRARY` before selecting Python to avoid incompatible paths inherited from PyInstaller parents.
- Focus matching is intentionally keyword-based (`codex`) and can produce false positives or misses; preserve the Store-window-title fallback unless replacing it with a verified stronger mechanism.
- Installer and packaging scripts stop with official `uv` installation guidance when `uv` is unavailable; they do not execute a remote bootstrap script. Exact external-tool pins are loaded from `scripts/dependency-versions.ps1`.
- CI validates tests, compilation, and that packaging produces a non-empty executable; it does not publish artifacts or replace installed/packaged GUI validation.

## Recommended reading order

Read `README.md`, then the constants and `load_usage()`/`normalize_usage()` path in `codex_usage_widget.py`, followed by `UsageWidget` startup/geometry/visibility methods. Read `scripts/start-codex-usage-widget.ps1` next to understand runtime selection and process cleanup, then the install/build scripts for distribution behavior.
