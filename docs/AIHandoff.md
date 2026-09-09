# AI Handoff — Codex Usage Widget v1.0.0

This handoff is for the Codex Usage Widget repository.

## Five-minute briefing

This is the v1.0.0 Windows-only Python/Tkinter widget for showing Codex usage while Codex is focused. It reads JSON from
the external `codex-cli-usage` command, converts utilization into remaining percentages, and displays 5-hour/weekly
windows and reset times. The header shows the exact visible label `v 1.0.0` immediately left of the close button. It
persists position, scales for narrow sidebars, hides when another application is focused, and refreshes asynchronously
every five minutes.

## Read first

1. `README.md` for supported behavior and launch/install commands.
2. `codex_usage_widget.py` for all application behavior.
3. `scripts/start-codex-usage-widget.ps1` for Python selection, debug mode, and environment handling; duplicate launches are blocked by the application mutex.
4. `pyproject.toml`, `scripts/install-windows.ps1`, and `scripts/build-exe.ps1` for packaging assumptions.
5. `git log` and current `git status` before treating work as complete.

## Conventions and constraints

- Target Windows 10/11, Python 3.10+, Tkinter, and an authenticated Codex installation.
- Keep GUI mutations on Tkinter's main thread; background work should only retrieve/parse data and schedule UI callbacks.
- Preserve quiet normal launch behavior and the visible debug path.
- Treat the persisted state file and user-home cache as machine-local data; do not commit or document its contents.
- Avoid casually replacing the usage parser, focus detection, geometry recovery, or launcher runtime ordering: these encode compatibility fixes.

## Current state

Tickets 01–03 provide the v1.0.0 version contract and label, cleaned launcher layout, and archived review/generated
artifact cleanup. Ticket 04 synchronizes this documentation with that state. The supported Microsoft Store Codex human
visual walkthrough passed with no issues noted. The separate non-Store Codex installation and validation is intentionally
skipped because it is not required for the supported environment and is not a release gate.

Inspect the diff and preserve unrelated user-owned changes before making further edits. Tickets 05–06 cover integrated
validation and supported visual sign-off; the GitHub review, merge, tag, and publication lifecycle is tracked externally by
PR #4 and issue #3.

## Launcher and distribution workflow

Keep `start-codex-usage-widget.vbs` at the repository root as the normal double-click entry point. Use the operational
PowerShell and CMD helpers under `scripts/` for installation, debugging, reset, and packaging. The standalone release
workflow runs `scripts/install-windows.ps1`, then `scripts/build-exe.ps1`, which produces `dist\CodexUsageWidget.exe`.
The target machine still needs Codex login state and a working `codex-cli-usage` installation.

## Common mistakes

- Do not assume the foreground process path is always readable; Store Codex may require title fallback.
- Do not turn the five-minute refresh into a blocking GUI call.
- Do not interpret the external tool's utilization percentage as remaining percentage; the widget intentionally flips it.
- For documentation-only changes, use focused scope checks and `git diff --check`. The repository has a focused test suite
  (`python -m pytest -q`), a compile check (`python -m compileall -q codex_usage_widget.py tests`), and a Windows CI
  workflow that performs a non-publishing packaging smoke test.
- Do not include credentials, tokens, private data, sensitive internal data, or machine-specific paths in continuity updates.

## Acceptance and remaining work

- Supported Microsoft Store Codex human visual walkthrough: passed with no issues noted.
- Separate non-Store Codex validation: intentionally skipped and not required for the supported environment; it is not a
  release gate.
- Integrated regression and packaging validation passed locally. The GitHub PR, merge, tag, and publication workflow is
  tracked externally by PR #4 and issue #3; the non-Store Codex check remains intentionally outside the release gate.
- The widget continues to depend on authenticated Codex state and the external `codex-cli-usage` tool; the standalone
  executable does not remove that prerequisite.
