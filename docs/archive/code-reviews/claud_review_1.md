# Code Review: codex-usage-widget

Scope: `codex_usage_widget.py` (main app), `install-windows.ps1`, `start-codex-usage-widget.ps1`, `reset-codex-usage-widget.ps1`, packaging/config files.

Severity scale: 🔴 High · 🟡 Medium · 🟢 Low / Nit

---

## Correctness & Robustness

- 🟡 **`load_usage()` retry sleeps on the UI-triggering thread's worker, but blocks for up to 3s per failed attempt with no cap on total wall time.** If `codex-cli-usage` hangs near the 30s timeout twice, a single refresh cycle can take ~63s. Not a crash, but worth a shorter timeout or single retry with backoff comment for future maintainers.
- 🟡 **`find_percent()` fraction-vs-percent heuristic is ambiguous at the boundary.** `0 <= value <= 1` is treated as a fraction (multiplied by 100), so a legitimate "1%" expressed as bare int/float `1` becomes `100%`. Low real-world likelihood given the upstream tool's format, but it's a silent-wrong-answer risk with no logging to catch it.
- 🟡 **`apply_start_geometry()` silently drops saved state if `save_state()` fails** (e.g., read-only disk, path permissions) — there's no try/except around `save_state`, so a `PermissionError` here will propagate up and crash the app at startup, which is a worse failure mode than just skipping the save.
- 🟢 **`geometry_from_state` / `clamp_geometry_to_work_area` don't validate `scale` is numeric**, only `x/y/width/height` are type-checked. A corrupted `scale` value (e.g., string) would pass through and later break `self.s()` math with a `TypeError` at first render call using that scale — though in practice `scale` is overwritten by `self.scale` in most callers, so this is fairly defensive already.
- 🟢 **`codex_has_focus()`'s boolean expression relies on operator precedence** (`and` binds tighter than `or`) to be correct: `process_name == "chatgpt.exe" and title_is_codex or (not process_name and title_is_codex)`. It *is* correct, but it's easy to misread on a skim — parenthesizing both branches explicitly would remove any doubt for future editors.

## Error Handling

- 🟢 **Broad `except Exception` in `refresh_worker` and in `__main__`** — appropriate here since these are top-level boundaries (background thread / process entry point) that must not crash silently, but worth a one-line comment noting that's intentional so a future refactor doesn't "fix" it into a narrower except and reintroduce crashes.
- 🟢 **`load_state()` swallows `OSError`/`ValueError` and returns `{}`** with no logging — reasonable for a "best effort, cosmetic state" file, but if this is ever extended to store anything more important, silent data loss on corruption would be worth surfacing somewhere (even just stderr).

## Security

- 🟡 **`install-windows.ps1` pipes a remote script straight into `iex`** (`irm https://astral.sh/uv/install.ps1 | iex`). This is standard practice for `uv`'s official installer, but it is unauthenticated remote code execution over HTTPS with no checksum pinning — flagging per standard supply-chain hygiene, not a bug in your code specifically.
- 🟢 **`load_usage()` resolves `codex-cli-usage` via `shutil.which`, i.e. whatever's first on `PATH`.** If a hostile binary with that name were earlier on PATH than the intended one, it would be executed silently. Low real-world risk on a single-user Windows box, but worth being aware of if this is ever distributed more widely.
- 🟢 **`Stop-ExistingWidgetProcesses` in `start-codex-usage-widget.ps1` matches and force-kills any process whose command line contains the widget script path via regex.** This is reasonably scoped (full path match, not a loose name match) but note it will kill *any* process, including ones the user didn't intend, if the command line happens to embed that exact path string (e.g., a text editor with the file open and path in its title/args — unlikely but worth knowing).

## Style / Maintainability

- 🟢 **`from re import match` imports a very generic name (`match`) into module scope.** It shadows nothing today, but `match` is also a Python 3.10+ soft keyword (structural pattern matching) and a common local variable name — importing `re` and calling `re.match(...)` would be clearer and less collision-prone.
- 🟢 **Magic coordinates throughout `UsageWidget.__init__`** (e.g. `self.make_label("5h", 48, 60, ...)`, button positions like `self.width - self.s(58)`) — functional, but a small layout constants block (or a simple row/column helper) would make future UI tweaks much less error-prone than hand-tuned pixel offsets scattered across ~40 lines.
- 🟢 **`rounded_rect()` builds its point list as a flat sequence of 24 bare numbers with no inline labeling of which corner each pair belongs to.** A list of `(x, y)` tuples (or short comments per corner) would make it easier to verify correctness at a glance.
- 🟢 **`normalize_usage`'s `for...else` pattern (fallback to `pick_window` when no direct key match) is a bit subtle** — works correctly, but a `for/else` on a dict key loop is an easy thing for a future reader to trip over; a short comment noting "else = no direct key found, fall back to fuzzy search" would help.
- 🟢 **`codex_usage_widget_state.json` (a user/machine-specific runtime artifact) is present in the shipped archive** even though it's correctly listed in `.gitignore`. Not a code bug, but worth excluding from distribution zips/releases so a stale absolute-position file doesn't get bundled by accident.

## Testing

- 🟡 **No automated tests included** for the pure-logic pieces that would benefit most from them: `find_percent`, `format_reset`, `normalize_usage`, `clamp_geometry_to_work_area`, `pick_window`. These are all deterministic, input→output functions with real edge cases (fraction vs. percent, missing keys, malformed timestamps) that are easy to regression-test without needing Tk or Windows APIs at all.

---

## Summary

No 🔴 high-severity issues found — this is a small, well-scoped desktop utility and the Windows-specific ctypes/Tk code is handled carefully (thread-safe UI updates via `root.after`, proper handle cleanup, defensive state-file parsing). The 🟡 items are worth a look (remote-script install pattern, percent-vs-fraction ambiguity, unbounded retry latency), but none are urgent. Most remaining notes are polish/maintainability nits rather than bugs.
