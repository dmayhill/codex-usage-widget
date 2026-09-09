# AI Handoff

This handoff is for the Codex Usage Widget repository.

## Five-minute briefing

This is a small Windows-only Python/Tkinter widget for showing Codex usage while Codex is focused. It reads JSON from the external `codex-cli-usage` command, converts utilization into remaining percentages, and displays 5-hour/weekly windows and reset times. It persists position, scales for narrow sidebars, hides when another application is focused, and refreshes asynchronously every five minutes.

## Read first

1. `README.md` for supported behavior and launch/install commands.
2. `codex_usage_widget.py` for all application behavior.
3. `scripts/start-codex-usage-widget.ps1` for Python selection, duplicate cleanup, debug mode, and environment handling.
4. `pyproject.toml`, `scripts/install-windows.ps1`, and `scripts/build-exe.ps1` for packaging assumptions.
5. `git log` and current `git status` before treating work as complete.

## Conventions and constraints

- Target Windows 10/11, Python 3.10+, Tkinter, and an authenticated Codex installation.
- Keep GUI mutations on Tkinter's main thread; background work should only retrieve/parse data and schedule UI callbacks.
- Preserve quiet normal launch behavior and the visible debug path.
- Treat the persisted state file and user-home cache as machine-local data; do not commit or document its contents.
- Avoid casually replacing the usage parser, focus detection, geometry recovery, or launcher runtime ordering: these encode compatibility fixes.

## Current state

Tickets 01–08 provide the reliability fixes, focused automated coverage, pinned non-executing installer/bootstrap guidance,
Windows CI validation, and synchronized project documentation. Ticket 09 added local packaged smoke evidence for the
integrated outcome. The worktree remains intentionally dirty; inspect the diff and preserve unrelated user-owned changes
before making further edits.

## Common mistakes

- Do not assume the foreground process path is always readable; Store Codex may require title fallback.
- Do not turn the five-minute refresh into a blocking GUI call.
- Do not interpret the external tool's utilization percentage as remaining percentage; the widget intentionally flips it.
- For documentation-only changes, use focused scope checks and `git diff --check`. The repository has a focused test suite
  (`python -m pytest -q`), a compile check (`python -m compileall -q codex_usage_widget.py tests`), and a Windows CI
  workflow that performs a non-publishing packaging smoke test.
- Do not include credentials, tokens, private data, sensitive internal data, or machine-specific paths in continuity updates.

## Unresolved or unverified

- Packaged native window-state checks passed for duplicate launch, position persistence, close during refresh, Store
  focus visibility, diagnostics, and missing-`uv` guidance. A human visual walkthrough remains an unverified release
  gate. The separate live non-Store Codex variant was intentionally skipped because it is not required for the
  supported Microsoft Store environment.
- CI and local packaging checks establish that the executable can be built and is non-empty; they do not establish full GUI
  acceptance on a target machine.
- Release ownership, distribution channel, and whether a standalone executable is the preferred artifact are not specified.
