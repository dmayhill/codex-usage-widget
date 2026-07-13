# Codex Usage Widget

A small Windows widget that keeps Codex usage visible while you work.

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
.\install-windows.ps1
```

That script installs `uv` if needed, installs `codex-cli-usage`, and checks that usage JSON can be read.

You can also install the dependency manually:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv tool install codex-cli-usage
codex-cli-usage json
```

## Run

Quiet launcher, recommended for normal use:

```powershell
.\start-codex-usage-widget.vbs
```

Visible launcher, useful for debugging startup errors:

```powershell
.\start-codex-usage-widget-debug.cmd
```

Reset-and-recenter launcher, useful if the widget gets remembered off-screen after an RDP session or monitor change:

```powershell
.\reset-codex-usage-widget-debug.cmd
```

The `.vbs` launcher starts the PowerShell launcher hidden, which avoids a startup console flash. The `-debug.cmd` launchers intentionally leave a visible console available when troubleshooting. The `.ps1` launcher prefers `pythonw.exe`, so the widget itself can run without leaving a console window open.

Every launch first closes any already-running `codex_usage_widget.py` instances, so repeated starts won’t leave duplicate widgets behind.

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
CODEX_PROCESS_KEYWORDS = ("codex",)
CODEX_WINDOW_KEYWORDS = ()
```

The saved window position is written to:

```text
codex_usage_widget_state.json
```

That file is intentionally ignored by Git.

## Packaging

For another Windows PC, the simplest deployment is:

1. Copy or clone this repository.
2. Run `.\install-windows.ps1`.
3. Run `.\start-codex-usage-widget.vbs`.

For a more app-like deployment, build a standalone executable:

```powershell
.\scripts\build-exe.ps1
```

That uses PyInstaller through `uvx` and writes:

```text
dist\CodexUsageWidget.exe
```

Even with the standalone widget executable, the target machine still needs Codex login state and a working `codex-cli-usage` install unless the widget is later changed to call Codex's usage endpoint directly.

## Credits

Usage data is provided by [`wakamex/codex-cli-usage`](https://github.com/wakamex/codex-cli-usage), published on PyPI as `codex-cli-usage`.

That project discovers and reads Codex rate-limit data from the same Codex/ChatGPT backend usage flow used by Codex tooling, and exposes it as terminal, statusline, daemon, and JSON output.

This widget is a Windows/Tkinter display layer on top of that tool. It does not vendor or copy `codex-cli-usage` source code.

## Notes

`codex-cli-usage` reports utilization percentages. This widget flips those values to show Codex-style remaining percentages.
