# AI Handoff

## Five-minute briefing

This is a small Windows-only Python/Tkinter widget for showing Codex usage while Codex is focused. It reads JSON from the external `codex-cli-usage` command, converts utilization into remaining percentages, and displays 5-hour/weekly windows and reset times. It persists position, scales for narrow sidebars, hides when another application is focused, and refreshes asynchronously every five minutes.

## Read first

1. `README.md` for supported behavior and launch/install commands.
2. `codex_usage_widget.py` for all application behavior.
3. `start-codex-usage-widget.ps1` for Python selection, duplicate cleanup, debug mode, and environment handling.
4. `pyproject.toml`, `install-windows.ps1`, and `scripts/build-exe.ps1` for packaging assumptions.
5. `git log` and current `git status` before treating work as complete.

## Conventions and constraints

- Target Windows 10/11, Python 3.10+, Tkinter, and an authenticated Codex installation.
- Keep GUI mutations on Tkinter's main thread; background work should only retrieve/parse data and schedule UI callbacks.
- Preserve quiet normal launch behavior and the visible debug path.
- Treat the persisted state file and user-home cache as machine-local data; do not commit or document its contents.
- Avoid casually replacing the usage parser, focus detection, geometry recovery, or launcher runtime ordering: these encode compatibility fixes.

## Current task

Validate the uncommitted Microsoft Store focus fallback and Tcl/Tk environment cleanup on the intended Windows setups. Then reconcile README wording and decide whether the untracked runtime log belongs in ignore rules or should be removed.

## Common mistakes

- Do not assume the foreground process path is always readable; Store Codex may require title fallback.
- Do not turn the five-minute refresh into a blocking GUI call.
- Do not interpret the external tool's utilization percentage as remaining percentage; the widget intentionally flips it.
- Do not run a broad test/build suite for a documentation-only change. No automated test suite or CI workflow is currently documented.
- Do not include credentials, tokens, private data, sensitive internal data, or machine-specific paths in continuity updates.

## Unresolved or unverified

- Manual runtime behavior on all supported Codex packaging variants is not verified in this repository.
- The README's launcher references and the current file set should be checked before release.
- Release ownership, distribution channel, and whether a standalone executable is the preferred artifact are not specified.
