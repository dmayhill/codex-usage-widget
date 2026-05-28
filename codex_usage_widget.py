import json
import os
import shutil
import subprocess
import sys
import threading
import time
import ctypes
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, NW, Button, Canvas, Label, Tk


REFRESH_SECONDS = 5 * 60
VISIBILITY_CHECK_MS = 250
SHOW_ONLY_WHEN_CODEX_FOCUSED = True
HIDE_ON_HOVER = False
RIGHT_CLICK_HIDE_SECONDS = 20
CODEX_PROCESS_KEYWORDS = ("codex",)
CODEX_WINDOW_KEYWORDS = ()
WIDTH = 420
HEIGHT = 190
BG = "#202124"
PANEL = "#2c2a2d"
BORDER = "#44474d"
TEXT = "#f2f2f2"
MUTED = "#a8a8ad"
ACCENT = "#d9d9df"
ERROR = "#ffb4a8"
STATE_PATH = Path(__file__).with_name("codex_usage_widget_state.json")


user32 = ctypes.windll.user32 if sys.platform == "win32" else None
kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def active_window_title():
    if user32 is None:
        return ""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def active_process_path():
    if user32 is None or kernel32 is None:
        return ""

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""

    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    if not process_id.value:
        return ""

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value)
    if not handle:
        return ""

    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
    finally:
        kernel32.CloseHandle(handle)

    return ""


def cursor_position():
    if user32 is None:
        return None
    point = POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        return None
    return point.x, point.y


def codex_has_focus():
    if not SHOW_ONLY_WHEN_CODEX_FOCUSED:
        return True
    process = active_process_path().lower()
    if any(keyword in process for keyword in CODEX_PROCESS_KEYWORDS):
        return True
    title = active_window_title().lower()
    return bool(CODEX_WINDOW_KEYWORDS) and any(keyword in title for keyword in CODEX_WINDOW_KEYWORDS)


def load_state():
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def rounded_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def find_percent(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(round(value * 100 if 0 <= value <= 1 else value))
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "")
        try:
            return int(round(float(cleaned)))
        except ValueError:
            return None
    if isinstance(value, dict):
        used = find_percent(value.get("pct"))
        if used is not None:
            return max(0, min(100, 100 - used))
        for key in (
            "percent_remaining",
            "remaining_percent",
            "remaining_pct",
            "percent_available",
            "available_percent",
            "remaining",
            "available",
        ):
            percent = find_percent(value.get(key))
            if percent is not None:
                return percent
        used = find_percent(value.get("used_percent") or value.get("usage_percent"))
        if used is not None:
            return max(0, min(100, 100 - used))
    return None


def format_reset(value):
    if value is None:
        return "--"
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        try:
            reset = datetime.fromtimestamp(timestamp)
            now = datetime.now()
            if reset.date() == now.date():
                return reset.strftime("%I:%M %p").lstrip("0")
            return reset.strftime("%b %d").replace(" 0", " ")
        except (OSError, ValueError):
            return "--"
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "--"
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone()
            now = datetime.now().astimezone()
            if parsed.date() == now.date():
                return parsed.strftime("%I:%M %p").lstrip("0")
            return parsed.strftime("%b %d").replace(" 0", " ")
        except ValueError:
            pass
        for prefix in ("resets ", "reset "):
            if text.lower().startswith(prefix):
                return text[len(prefix) :]
        return text
    if isinstance(value, dict):
        for key in (
            "reset_at",
            "resets_at",
            "reset_time",
            "reset",
            "resets",
            "window_reset",
        ):
            reset = format_reset(value.get(key))
            if reset != "--":
                return reset
    return "--"


def walk(obj):
    yield obj
    if isinstance(obj, dict):
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk(value)


def score_window(obj, labels):
    if not isinstance(obj, dict):
        return -1
    haystack = " ".join(str(v).lower() for v in obj.values() if isinstance(v, (str, int, float)))
    keys = " ".join(str(k).lower() for k in obj.keys())
    blob = f"{keys} {haystack}"
    return sum(1 for label in labels if label in blob)


def pick_window(data, labels):
    candidates = [item for item in walk(data) if isinstance(item, dict)]
    candidates.sort(key=lambda item: score_window(item, labels), reverse=True)
    for item in candidates:
        if score_window(item, labels) <= 0:
            continue
        percent = find_percent(item)
        if percent is not None:
            return percent, format_reset(item)
    return None, "--"


def normalize_usage(data):
    if isinstance(data, dict):
        for key in ("primary_window", "primary", "session", "five_hour", "5h"):
            if key in data:
                session_percent = find_percent(data[key])
                session_reset = format_reset(data[key])
                break
        else:
            session_percent, session_reset = pick_window(data, ("5h", "5-hour", "session", "primary"))

        for key in ("secondary_window", "secondary", "weekly", "week", "7d"):
            if key in data:
                weekly_percent = find_percent(data[key])
                weekly_reset = format_reset(data[key])
                break
        else:
            weekly_percent, weekly_reset = pick_window(data, ("7d", "7-day", "week", "weekly", "secondary"))

        plan = data.get("plan") or data.get("account_plan") or data.get("subscription") or ""
    else:
        session_percent, session_reset = None, "--"
        weekly_percent, weekly_reset = None, "--"
        plan = ""

    return {
        "plan": str(plan).title() if plan else "",
        "session_percent": session_percent,
        "session_reset": session_reset,
        "weekly_percent": weekly_percent,
        "weekly_reset": weekly_reset,
    }


def load_usage():
    command = shutil.which("codex-cli-usage")
    if command:
        result = subprocess.run(
            [command, "json"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return normalize_usage(json.loads(result.stdout))

    cache_path = Path.home() / ".codex" / "usage-limits.json"
    if cache_path.exists():
        return normalize_usage(json.loads(cache_path.read_text(encoding="utf-8")))

    raise RuntimeError("No usage data yet. Install codex-cli-usage, then run codex-cli-usage json.")


class UsageWidget:
    def __init__(self):
        self.root = Tk()
        self.root.title("Codex Usage")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.apply_start_geometry()
        self.transparent = "#010203"
        self.root.configure(bg=self.transparent)
        try:
            self.root.wm_attributes("-transparentcolor", self.transparent)
        except Exception:
            self.root.configure(bg=BG)

        self.drag_handles = []
        self.canvas = Canvas(self.root, width=WIDTH, height=HEIGHT, bg=self.transparent, highlightthickness=0)
        self.canvas.pack(fill=BOTH, expand=True)
        rounded_rect(self.canvas, 1, 1, WIDTH - 2, HEIGHT - 2, 18, fill=PANEL, outline=BORDER, width=1)

        self.title = self.make_label("Codex Usage", 22, 20, font=("Segoe UI", 14, "bold"))
        self.plan = self.make_label("", 170, 22, font=("Segoe UI", 9), fg=MUTED)
        self.status = self.make_label("Loading...", 22, 140, font=("Segoe UI", 8), fg=MUTED)
        self.status.configure(wraplength=185, justify="left")
        self.hint = self.make_label("Right-click to hide 20s", 218, 140, font=("Segoe UI", 8), fg=MUTED)

        self.make_label("5h", 48, 60, font=("Segoe UI", 12, "bold"))
        self.session_percent = self.make_label("--", 242, 60, font=("Segoe UI", 12, "bold"), anchor="e", width=4)
        self.session_reset = self.make_label("--", 290, 60, font=("Segoe UI", 11), fg=MUTED, anchor="w", width=8)

        self.make_label("Weekly", 48, 98, font=("Segoe UI", 12, "bold"))
        self.weekly_percent = self.make_label("--", 242, 98, font=("Segoe UI", 12, "bold"), anchor="e", width=4)
        self.weekly_reset = self.make_label("--", 290, 98, font=("Segoe UI", 11), fg=MUTED, anchor="w", width=8)

        self.close_button = Button(
            self.root,
            text="x",
            bd=0,
            highlightthickness=0,
            bg=PANEL,
            fg=MUTED,
            activebackground=PANEL,
            activeforeground=TEXT,
            command=self.close,
            font=("Segoe UI", 10),
        )
        self.canvas.create_window(WIDTH - 28, 22, window=self.close_button, width=22, height=22)

        self.refresh_button = Button(
            self.root,
            text="refresh",
            bd=0,
            highlightthickness=0,
            bg=PANEL,
            fg=MUTED,
            activebackground=PANEL,
            activeforeground=TEXT,
            command=self.refresh_async,
            font=("Segoe UI", 8),
        )
        self.canvas.create_window(WIDTH - 58, 150, window=self.refresh_button, width=60, height=22)

        self.drag_x = 0
        self.drag_y = 0
        self.hidden_for_hover = False
        self.hidden_until = 0
        self.last_bounds = None
        self.bind_drag_handle(self.canvas)
        for handle in self.drag_handles:
            self.bind_drag_handle(handle)
        self.root.bind_all("<ButtonPress-3>", self.hide_temporarily)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def apply_start_geometry(self):
        state = load_state()
        x = state.get("x")
        y = state.get("y")

        if not isinstance(x, int) or not isinstance(y, int):
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = 32
            y = max(32, screen_height - HEIGHT - 96)

        self.root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    def make_label(self, text, x, y, font, fg=TEXT, anchor="w", width=0):
        label = Label(self.root, text=text, bg=PANEL, fg=fg, font=font, anchor=anchor, width=width)
        self.canvas.create_window(x, y, window=label, anchor=NW)
        self.drag_handles.append(label)
        return label

    def bind_drag_handle(self, widget):
        widget.bind("<ButtonPress-1>", self.start_drag)
        widget.bind("<B1-Motion>", self.drag)
        widget.bind("<ButtonRelease-1>", self.save_position)
        widget.bind("<Enter>", self.hide_for_hover)

    def start_drag(self, event):
        self.drag_x = event.x
        self.drag_y = event.y

    def drag(self, event):
        x = self.root.winfo_x() + event.x - self.drag_x
        y = self.root.winfo_y() + event.y - self.drag_y
        self.root.geometry(f"+{x}+{y}")

    def save_position(self, _event=None):
        save_state(
            {
                "x": self.root.winfo_x(),
                "y": self.root.winfo_y(),
                "width": WIDTH,
                "height": HEIGHT,
            }
        )

    def close(self):
        self.save_position()
        self.root.destroy()

    def current_bounds(self):
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        return x, y, x + WIDTH, y + HEIGHT

    def cursor_inside_last_bounds(self):
        if self.last_bounds is None:
            return False
        position = cursor_position()
        if position is None:
            return False
        x, y = position
        left, top, right, bottom = self.last_bounds
        return left <= x <= right and top <= y <= bottom

    def hide_for_hover(self, _event=None):
        if not HIDE_ON_HOVER or self.hidden_for_hover:
            return
        self.last_bounds = self.current_bounds()
        self.hidden_for_hover = True
        self.root.withdraw()

    def hide_temporarily(self, _event=None):
        self.save_position()
        self.last_bounds = self.current_bounds()
        self.hidden_until = time.time() + RIGHT_CLICK_HIDE_SECONDS
        self.root.withdraw()

    def update_visibility(self):
        focused = codex_has_focus()
        timed_hidden = time.time() < self.hidden_until
        hover_blocked = self.hidden_for_hover and self.cursor_inside_last_bounds()

        if not focused:
            if self.root.state() != "withdrawn":
                self.last_bounds = self.current_bounds()
                self.root.withdraw()
            self.root.after(VISIBILITY_CHECK_MS, self.update_visibility)
            return

        if timed_hidden or hover_blocked:
            self.root.after(VISIBILITY_CHECK_MS, self.update_visibility)
            return

        self.hidden_for_hover = False
        if self.root.state() == "withdrawn":
            self.root.deiconify()
            self.root.attributes("-topmost", True)
        self.root.after(VISIBILITY_CHECK_MS, self.update_visibility)

    def set_status(self, message, error=False):
        self.status.configure(text=message, fg=ERROR if error else MUTED)

    def apply_usage(self, usage):
        plan = usage.get("plan", "")
        self.plan.configure(text=plan)

        session = usage.get("session_percent")
        weekly = usage.get("weekly_percent")
        self.session_percent.configure(text=f"{session}%" if session is not None else "--")
        self.weekly_percent.configure(text=f"{weekly}%" if weekly is not None else "--")
        self.session_reset.configure(text=usage.get("session_reset") or "--")
        self.weekly_reset.configure(text=usage.get("weekly_reset") or "--")
        self.set_status("Updated " + datetime.now().strftime("%I:%M %p").lstrip("0"))

    def refresh_async(self):
        self.set_status("Refreshing...")
        thread = threading.Thread(target=self.refresh_worker, daemon=True)
        thread.start()

    def refresh_worker(self):
        try:
            usage = load_usage()
        except Exception as exc:
            message = str(exc)
            self.root.after(0, lambda: self.set_status(message, error=True))
            return
        self.root.after(0, lambda: self.apply_usage(usage))

    def schedule_refresh(self):
        self.refresh_async()
        self.root.after(REFRESH_SECONDS * 1000, self.schedule_refresh)

    def run(self):
        self.schedule_refresh()
        self.update_visibility()
        self.root.mainloop()


if __name__ == "__main__":
    UsageWidget().run()
