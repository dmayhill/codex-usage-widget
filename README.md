# Codex Usage Widget

A small Windows widget that keeps Codex usage visible while you work.

This is the `v1.0.0` release. The widget displays the visible version label
`v 1.0.0` in small, muted text immediately to the left of the `x` close button.

It shows Codex-style remaining usage for:

- `5h`
- `Weekly`
- reset time/date
- last refresh time

The widget is always on top, remembers its position, refreshes every 5 minutes, and hides when Codex is not the focused app.

## Screenshot

No screenshot is bundled yet. The widget is a compact dark panel designed to sit near the lower-left Codex settings area.

## Requirements

- Windows 10 or Windows 11
- Codex already logged in on the machine
- Python 3 with Tkinter, or the bundled Codex Python runtime
- [`uv`](https://docs.astral.sh/uv/)
- [`codex-cli-usage`](https://github.com/wakamex/codex-cli-usage)

The widget itself uses only the Python standard library. `codex-cli-usage` is used as the usage data source.

## Install

Open PowerShell in this folder and run:

```powershell
.\scripts\install-windows.ps1
```

That script installs the pinned `codex-cli-usage` version, and checks that usage JSON can be read. If `uv` is missing, it prints official installation guidance and exits without downloading or executing a remote script.

You can also install the dependency manually:

```powershell
winget install --id=astral-sh.uv -e
uv tool install --force codex-cli-usage==0.1.7
codex-cli-usage json
```

The installer and build pins are kept in [`scripts/dependency-versions.ps1`](scripts/dependency-versions.ps1).

If `uv` is missing, both the installer and packaging script stop and print the official installation page plus the
official Windows package-manager command. They do not download or execute a remote installation script.

## Run

Quiet launcher, recommended for normal use:

```powershell
.\start-codex-usage-widget.vbs
```

Visible launcher, useful for debugging startup errors:

```powershell
.\scripts\start-codex-usage-widget-debug.cmd
```

Reset-and-recenter launcher, useful if the widget gets remembered off-screen after an RDP session or monitor change:

```powershell
.\scripts\reset-codex-usage-widget-debug.cmd
```

The `.vbs` launcher starts the PowerShell launcher hidden, which avoids a startup console flash. The `-debug.cmd` launchers intentionally leave a visible console available when troubleshooting. Quiet mode only uses `pythonw.exe`; it does not fall back to console-subsystem Python, so a missing GUI Python runtime fails quietly instead of flashing a command window.

The widget uses a named single-instance mutex, so repeated starts do not create duplicate widgets. The launcher selects a
Python runtime and starts the widget from the repository root.

## Repository layout

The committed operational layout keeps the quiet VBS entry point at the repository root and places the PowerShell and CMD
helpers under `scripts/`:

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
  build-exe.ps1
  dependency-versions.ps1
  install-windows.ps1
  reset-codex-usage-widget-debug.cmd
  reset-codex-usage-widget.ps1
  start-codex-usage-widget-debug.cmd
  start-codex-usage-widget.ps1
tests/
```

Run the root-level `.vbs` launcher for normal use. Use the helpers under `scripts/` for installation, debugging, reset,
and packaging; there are no root-level PowerShell or CMD launchers.

## Behavior

The widget is configured to:

- show only while the focused app is `codex.exe`, or `ChatGPT.exe` with a `Codex`/`ChatGPT Codex` title; Store packaging uses the constrained title fallback
- remember its last dragged position
- clamp restored positions to the current monitor work area
- preserve the last known good position separately from the most recent attempt
- fall back to a centered position when no valid saved location exists
- refresh automatically every 5 minutes
- hide for 20 seconds when you right-click it, so you can click whatever is behind it

The most useful switches live near the top of `codex_usage_widget.py`:

```python
REFRESH_SECONDS = 5 * 60
SHOW_ONLY_WHEN_CODEX_FOCUSED = True
HIDE_ON_HOVER = False
RIGHT_CLICK_HIDE_SECONDS = 20
CODEX_WINDOW_TITLE_PATTERNS = (
    r"^codex(?:\s|$)",
    r"^chatgpt\s+codex(?:\s|$)",
)
CODEX_PACKAGE_MARKER = "\\windowsapps\\openai.codex_"
```

The saved window position is written to:

```text
source run:   <repository>\codex_usage_widget_state.json
packaged run: %LOCALAPPDATA%\CodexUsageWidget\codex_usage_widget_state.json
```

Source runs keep the state file beside `codex_usage_widget.py`. Packaged runs keep it in the per-user local
application-data directory. If a packaged executable finds the old state file beside the executable, it migrates that
state to the local-application-data path. State files are machine-local and intentionally ignored by Git.

When startup, state persistence, or usage refresh fails, the widget writes bounded diagnostics beside the active state
file:

```text
source run:   <repository>\codex_usage_widget.log
packaged run: %LOCALAPPDATA%\CodexUsageWidget\codex_usage_widget.log
```

The log rotates at 256 KB and keeps one backup. Entries contain a timestamp, phase, exception type, and relevant paths;
usage payloads and exception messages are not copied into the log. Runtime logs and their rotated backups are ignored by
Git.

## Packaging and standalone distribution

For source deployment on another Windows PC:

1. Copy or clone this repository.
2. Run `.\scripts\install-windows.ps1`.
3. Run `.\start-codex-usage-widget.vbs`.

For a more app-like deployment, build a standalone executable:

```powershell
.\scripts\build-exe.ps1
```

That uses the pinned PyInstaller version through `uvx` (or `uv tool run`) and writes:

```text
dist\CodexUsageWidget.exe
```

Even with the standalone widget executable, the target machine still needs Codex login state and a working `codex-cli-usage` install unless the widget is later changed to call Codex's usage endpoint directly.

For the v1.0.0 standalone distribution workflow, run the installer check and `.\scripts\build-exe.ps1` on the build machine,
then distribute `dist\CodexUsageWidget.exe` as the executable release artifact. The generated `build/`, `dist/`, and
PyInstaller spec files remain local build outputs and are ignored by Git.

## Validation

Focused automated tests cover usage normalization, state migration and validation, diagnostics, focus detection, and
launcher/packaging assumptions. Run them from the repository root with:

```powershell
python -m pytest -q
python -m compileall -q codex_usage_widget.py tests
```

The Windows CI workflow runs on pushes and pull requests. It uses Python 3.12, `pytest==8.4.1`, compiles the Python
sources, installs `uv==0.11.17` for the packaging smoke test, builds with the pinned PyInstaller version, and verifies
that `dist\CodexUsageWidget.exe` exists and is non-empty. The workflow does not publish a release.

For v1.0.0 release acceptance, the supported Microsoft Store Codex human visual walkthrough passed with no issues noted.
The separate non-Store Codex installation and validation is intentionally skipped because it is not required for the
supported environment and is not a release gate. Before distributing the standalone executable, still run the installer
check, confirm `codex-cli-usage json` returns usage data on the target machine, and run `.\scripts\build-exe.ps1`.

## Credits

Usage data is provided by [`wakamex/codex-cli-usage`](https://github.com/wakamex/codex-cli-usage), published on PyPI as `codex-cli-usage`.

That project discovers and reads Codex rate-limit data from the same Codex/ChatGPT backend usage flow used by Codex tooling, and exposes it as terminal, statusline, daemon, and JSON output.

This widget is a Windows/Tkinter display layer on top of that tool. It does not vendor or copy `codex-cli-usage` source code.

## Notes

`codex-cli-usage` reports utilization percentages. This widget flips those values to show Codex-style remaining percentages.
