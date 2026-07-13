# Architecture

## High-level design

The application is a single Python/Tkinter process with three concerns:

1. Read usage data from `codex-cli-usage json` or a generic local fallback cache.
2. Normalize heterogeneous usage JSON into session/weekly percentages and reset labels.
3. Render and manage a Windows desktop widget, including focus visibility, scaling, persistence, and refresh scheduling.

PowerShell, CMD, and VBScript files provide installation, launch, debug, reset, and packaging workflows around the Python entry point.

## Important files

- `codex_usage_widget.py`: application entry point and all widget, Windows API, usage parsing, persistence, and refresh logic.
- `start-codex-usage-widget.ps1`: stops duplicate instances, removes incompatible Tcl/Tk environment overrides, selects a Python runtime, and starts the widget.
- `start-codex-usage-widget.vbs`: starts the PowerShell launcher hidden for normal use.
- `start-codex-usage-widget-debug.cmd`: invokes the launcher with a visible troubleshooting console.
- `reset-codex-usage-widget.ps1` and `reset-codex-usage-widget-debug.cmd`: start with `--reset-position`.
- `install-windows.ps1`: installs `uv`/`codex-cli-usage` as needed and checks JSON access.
- `scripts/build-exe.ps1`: invokes PyInstaller through `uvx`.
- `pyproject.toml`: package metadata and Python/Ruff configuration.

## Data flow

`UsageWidget.schedule_refresh()` starts an asynchronous refresh. `load_usage()` invokes `codex-cli-usage json`, retries once after a transient subprocess/timeout/JSON error, and passes decoded data to `normalize_usage()`. If the command is unavailable, it attempts a generic usage cache under the user's home configuration area. The normalized values are applied on the Tkinter thread by `apply_usage()`; failures preserve last-known data when available.

On startup, geometry is loaded from the adjacent `codex_usage_widget_state.json`, clamped to a monitor work area, and restored or centered. Drag release saves the current geometry and a `last_good` position. Visibility is checked every 250 ms using the foreground process path and, where needed, foreground window title. Right-click temporarily withdraws the widget for 20 seconds.

## Key design decisions and constraints

- Standard-library Python keeps the widget lightweight; `codex-cli-usage` is an external data source rather than vendored code.
- Tkinter updates remain on the GUI thread; usage retrieval runs in a daemon worker thread.
- Windows APIs are accessed through `ctypes`; non-Windows execution has limited fallback behavior and is not the primary target.
- Geometry is persisted separately from source and ignored by Git because it is machine/user-specific.
- Launchers prefer `pythonw.exe` for normal use and preserve a visible debug path for diagnosing startup failures.
- The current launcher clears `TCL_LIBRARY` and `TK_LIBRARY` before selecting Python to avoid incompatible paths inherited from PyInstaller parents.
- Focus matching is intentionally keyword-based (`codex`) and can produce false positives or misses; preserve the Store-window-title fallback unless replacing it with a verified stronger mechanism.

## Recommended reading order

Read `README.md`, then the constants and `load_usage()`/`normalize_usage()` path in `codex_usage_widget.py`, followed by `UsageWidget` startup/geometry/visibility methods. Read `start-codex-usage-widget.ps1` next to understand runtime selection and process cleanup, then the install/build scripts for distribution behavior.
