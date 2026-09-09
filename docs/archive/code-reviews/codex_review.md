# Code Review

Scope: whole-codebase review at `main` (`c016deb`). `main...HEAD` is empty, so this is not a diff-only review. Severity ranks impact if the affected path is used.

- **[P1 — High] Packaged builds do not persist widget position.** [`codex_usage_widget.py:46`](codex_usage_widget.py#L46) derives `STATE_PATH` from `__file__`. In the documented PyInstaller `--onefile` build, `__file__` resolves under PyInstaller's temporary extraction directory, which changes (and can be deleted) on each launch. Consequently, `save_state()` at [`codex_usage_widget.py:148`](codex_usage_widget.py#L148) does not provide the persistent position promised by the README for the standalone executable. Store state in a stable per-user location such as `%LOCALAPPDATA%\\CodexUsageWidget` (or use `sys.executable`'s directory for a portable build), and migrate any existing state if appropriate.

- **[P2 — Medium] A close during a refresh can leave an unhandled background-thread exception.** `refresh_worker()` calls `self.root.after(...)` from its worker thread at [`codex_usage_widget.py:703`](codex_usage_widget.py#L703) and [`codex_usage_widget.py:706`](codex_usage_widget.py#L706). If the user closes the window after the subprocess starts, `self.root.destroy()` at [`codex_usage_widget.py:607`](codex_usage_widget.py#L607) can run before either callback is scheduled; Tk then raises because its interpreter has been destroyed. Track shutdown and avoid scheduling callbacks once closing begins (or catch `tkinter.TclError` around the `after` calls) so a normal close is clean.

- **[P3 — Low] Static checks will report unused code.** `os` is imported but never used at [`codex_usage_widget.py:3`](codex_usage_widget.py#L3), and `ACCENT` is declared but never referenced at [`codex_usage_widget.py:44`](codex_usage_widget.py#L44). Remove them, or use `ACCENT` for an intended visual element. This keeps the project clean under the configured Ruff tooling.

Verification: `python -m py_compile codex_usage_widget.py` passed. No automated test suite is currently present.
