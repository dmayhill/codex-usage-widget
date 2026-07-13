import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import ctypes
import traceback
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from re import match
from tkinter import BOTH, NW, Button, Canvas, Label, TclError, Tk


REFRESH_SECONDS = 5 * 60
REFRESH_RETRY_SECONDS = 3
VISIBILITY_CHECK_MS = 250
# The Microsoft Store app's foreground process is not reliably observable.
# CODEX_WINDOW_TITLE_PATTERNS provides the constrained fallback needed for it.
SHOW_ONLY_WHEN_CODEX_FOCUSED = True
HIDE_ON_HOVER = False
RIGHT_CLICK_HIDE_SECONDS = 20
# Microsoft Store apps can deny foreground process-path queries. Only accept
# titles that identify the Codex app, rather than any title containing codex.
CODEX_WINDOW_TITLE_PATTERNS = (
    r"^codex(?:\s|$)",
    r"^chatgpt\s+codex(?:\s|$)",
)
CODEX_PACKAGE_MARKER = "\\windowsapps\\openai.codex_"
BASE_WIDTH = 420
BASE_HEIGHT = 190
BASE_SCREEN_WIDTH = 1920
MAX_SIDEBAR_WIDTH = 292
MIN_SCALE = 0.68
MAX_SCALE = 1.0
BG = "#202124"
PANEL = "#2c2a2d"
BORDER = "#44474d"
TEXT = "#f2f2f2"
MUTED = "#a8a8ad"
ERROR = "#ffb4a8"
STATE_FILE_NAME = "codex_usage_widget_state.json"
APP_STATE_DIRECTORY = "CodexUsageWidget"
SOURCE_STATE_PATH = Path(__file__).with_name(STATE_FILE_NAME)
CREATE_NO_WINDOW = 0x08000000


user32 = ctypes.windll.user32 if sys.platform == "win32" else None
kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MONITOR_DEFAULTTONEAREST = 2
SPI_GETWORKAREA = 0x0030
SM_CXSCREEN = 0
SM_CYSCREEN = 1


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


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
    process_path = active_process_path().lower()
    process_name = Path(process_path).name
    if process_name == "codex.exe":
        return True
    if process_name == "chatgpt.exe" and CODEX_PACKAGE_MARKER in process_path:
        return True
    title = active_window_title().strip().lower()
    title_is_codex = any(match(pattern, title) for pattern in CODEX_WINDOW_TITLE_PATTERNS)
    return (process_name == "chatgpt.exe" and title_is_codex) or (not process_name and title_is_codex)


def state_path():
    if not getattr(sys, "frozen", False):
        return legacy_state_path()
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local_app_data / APP_STATE_DIRECTORY / STATE_FILE_NAME


def legacy_state_path():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).with_name(STATE_FILE_NAME)
    return SOURCE_STATE_PATH


def read_state(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_state(path=None):
    path = path or state_path()
    legacy_path = legacy_state_path()
    try:
        path_exists = path.exists()
        legacy_exists = legacy_path.exists()
    except OSError:
        return {}

    if path_exists or not getattr(sys, "frozen", False) or not legacy_exists:
        return read_state(path)

    state = read_state(legacy_path)
    if state:
        save_state(state, path)
    return state


def save_state(state, path=None):
    path = path or state_path()
    temporary_path = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(state, temporary_file, indent=2)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
        return True
    except OSError:
        return False
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def clamp(value, lower, upper):
    return max(lower, min(upper, value))


def geometry_from_state(state):
    if not isinstance(state, dict):
        return None
    keys = ("x", "y", "width", "height", "scale")
    if all(key in state for key in keys):
        return {key: state.get(key) for key in keys}
    return None


def state_with_geometry(state, geometry, include_last_good=False):
    payload = dict(state) if isinstance(state, dict) else {}
    payload.update(geometry)
    if include_last_good:
        payload["last_good"] = dict(geometry)
    return payload


def default_work_area():
    if sys.platform != "win32" or user32 is None:
        return 0, 0, BASE_SCREEN_WIDTH, BASE_HEIGHT * 3
    rect = RECT()
    if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
        return rect.left, rect.top, rect.right, rect.bottom
    return 0, 0, user32.GetSystemMetrics(SM_CXSCREEN), user32.GetSystemMetrics(SM_CYSCREEN)


def work_area_for_point(point=None):
    if sys.platform != "win32" or user32 is None:
        return default_work_area()

    if point is None:
        point = cursor_position() or (0, 0)

    try:
        x, y = point
    except (TypeError, ValueError):
        x, y = 0, 0

    monitor = user32.MonitorFromPoint(POINT(x, y), MONITOR_DEFAULTTONEAREST)
    if monitor:
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            work = info.rcWork
            return work.left, work.top, work.right, work.bottom

    return default_work_area()


def clamp_geometry_to_work_area(geometry, work_area):
    if not geometry:
        return None

    x = geometry.get("x")
    y = geometry.get("y")
    width = geometry.get("width")
    height = geometry.get("height")
    scale = geometry.get("scale")

    if not all(isinstance(value, int) for value in (x, y, width, height)):
        return None

    left, top, right, bottom = work_area
    max_x = max(left, right - width)
    max_y = max(top, bottom - height)

    return {
        "x": clamp(x, left, max_x),
        "y": clamp(y, top, max_y),
        "width": width,
        "height": height,
        "scale": scale,
    }


def centered_geometry(width, height, work_area):
    left, top, right, bottom = work_area
    work_width = max(1, right - left)
    work_height = max(1, bottom - top)
    x = left + max(0, (work_width - width) // 2)
    y = top + max(0, (work_height - height) // 2)
    return {"x": x, "y": y, "width": width, "height": height, "scale": None}


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
    if not command and sys.platform == "win32":
        uv_tool_command = Path.home() / ".local" / "bin" / "codex-cli-usage.exe"
        if uv_tool_command.exists():
            command = str(uv_tool_command)

    if command:
        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = CREATE_NO_WINDOW

        last_error = None
        for attempt in range(2):
            try:
                result = subprocess.run(
                    [command, "json"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True,
                    startupinfo=startupinfo,
                    creationflags=creationflags,
                )
                return normalize_usage(json.loads(result.stdout))
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(REFRESH_RETRY_SECONDS)

        raise last_error

    cache_path = Path.home() / ".codex" / "usage-limits.json"
    if cache_path.exists():
        return normalize_usage(json.loads(cache_path.read_text(encoding="utf-8")))

    raise RuntimeError("No usage data yet. Install codex-cli-usage, then run codex-cli-usage json.")


class UsageWidget:
    def __init__(self):
        self.root = Tk()
        self.scale = self.display_scale()
        self.width = self.s(BASE_WIDTH)
        self.height = self.s(BASE_HEIGHT)
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
        self.canvas = Canvas(self.root, width=self.width, height=self.height, bg=self.transparent, highlightthickness=0)
        self.canvas.pack(fill=BOTH, expand=True)
        rounded_rect(self.canvas, 1, 1, self.width - 2, self.height - 2, self.s(18), fill=PANEL, outline=BORDER, width=1)

        self.title = self.make_label("Codex Usage", 22, 20, font=self.font(14, "bold"))
        self.plan = self.make_label("", 170, 22, font=self.font(9), fg=MUTED)
        self.status = self.make_label("Loading...", 22, 140, font=self.font(8), fg=MUTED)
        self.status.configure(wraplength=self.s(130), justify="left")
        self.hint = self.make_label("Right-click\nto hide 20s", 210, 132, font=self.font(8), fg=MUTED)
        self.hint.configure(justify="center", wraplength=self.s(62))

        self.make_label("5h", 48, 60, font=self.font(12, "bold"))
        self.session_percent = self.make_label("--", 242, 60, font=self.font(12, "bold"), anchor="e", width=4)
        self.session_reset = self.make_label("--", 290, 60, font=self.font(11), fg=MUTED, anchor="w", width=8)

        self.make_label("Weekly", 48, 98, font=self.font(12, "bold"))
        self.weekly_percent = self.make_label("--", 242, 98, font=self.font(12, "bold"), anchor="e", width=4)
        self.weekly_reset = self.make_label("--", 290, 98, font=self.font(11), fg=MUTED, anchor="w", width=8)

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
            font=self.font(10),
        )
        self.canvas.create_window(self.width - self.s(28), self.s(22), window=self.close_button, width=self.s(22), height=self.s(22))

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
            font=self.font(8),
        )
        self.canvas.create_window(self.width - self.s(58), self.s(150), window=self.refresh_button, width=self.s(60), height=self.s(22))

        self.drag_x = 0
        self.drag_y = 0
        self.hidden_for_hover = False
        self.hidden_until = 0
        self.last_bounds = None
        self.last_usage = None
        self.refreshing = False
        self.closing = False
        self.bind_drag_handle(self.canvas)
        for handle in self.drag_handles:
            self.bind_drag_handle(handle)
        self.root.bind_all("<ButtonPress-3>", self.hide_temporarily)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def display_scale(self):
        screen_width = self.root.winfo_screenwidth()
        screen_scale = screen_width / BASE_SCREEN_WIDTH
        sidebar_scale = MAX_SIDEBAR_WIDTH / BASE_WIDTH
        return max(MIN_SCALE, min(MAX_SCALE, screen_scale, sidebar_scale))

    def s(self, value):
        return int(round(value * self.scale))

    def font(self, size, weight=None):
        scaled_size = max(7, int(round(size * self.scale)))
        if weight:
            return ("Segoe UI", scaled_size, weight)
        return ("Segoe UI", scaled_size)

    def apply_start_geometry(self):
        state = load_state()
        current = geometry_from_state(state)
        last_good = geometry_from_state(state.get("last_good")) if isinstance(state, dict) else None
        work_area = work_area_for_point((current["x"], current["y"])) if current else work_area_for_point()
        selected = clamp_geometry_to_work_area(current, work_area) if current else None

        if selected is None:
            selected = clamp_geometry_to_work_area(last_good, work_area) if last_good else None

        if selected is None:
            selected = centered_geometry(self.width, self.height, work_area)
            selected["scale"] = self.scale

        self.root.geometry(f"{self.width}x{self.height}+{selected['x']}+{selected['y']}")
        if isinstance(state, dict):
            save_state(state_with_geometry(state, selected, include_last_good=False))

    def make_label(self, text, x, y, font, fg=TEXT, anchor="w", width=0):
        label = Label(self.root, text=text, bg=PANEL, fg=fg, font=font, anchor=anchor, width=width)
        self.canvas.create_window(self.s(x), self.s(y), window=label, anchor=NW)
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
        geometry = {
            "x": self.root.winfo_x(),
            "y": self.root.winfo_y(),
            "width": self.width,
            "height": self.height,
            "scale": self.scale,
        }
        payload = state_with_geometry(load_state(), geometry, include_last_good=True)
        save_state(payload)

    def reset_position(self):
        work_area = work_area_for_point()
        geometry = centered_geometry(self.width, self.height, work_area)
        geometry["scale"] = self.scale
        self.root.geometry(f"{self.width}x{self.height}+{geometry['x']}+{geometry['y']}")
        save_state(state_with_geometry(load_state(), geometry, include_last_good=True))

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.save_position()
        self.root.destroy()

    def current_bounds(self):
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        return x, y, x + self.width, y + self.height

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
        self.last_usage = usage
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
        if self.refreshing:
            return
        self.refreshing = True
        self.set_status("Refreshing...")
        thread = threading.Thread(target=self.refresh_worker, daemon=True)
        thread.start()

    def finish_refresh(self):
        self.refreshing = False

    def schedule_ui_callback(self, callback):
        if self.closing:
            return False

        def run_callback():
            if not self.closing:
                callback()

        try:
            self.root.after(0, run_callback)
        except (RuntimeError, TclError):
            return False
        return True

    def apply_refresh_error(self, exc):
        if self.last_usage:
            self.set_status("Refresh failed\nlast data shown", error=True)
            return

        if isinstance(exc, subprocess.CalledProcessError):
            message = "Usage tool failed. Try reopening Codex."
        elif isinstance(exc, subprocess.TimeoutExpired):
            message = "Usage refresh timed out."
        else:
            message = "Could not load usage data."
        self.set_status(message, error=True)

    def refresh_worker(self):
        try:
            usage = load_usage()
        except Exception as exc:
            self.schedule_ui_callback(lambda: self.apply_refresh_error(exc))
            self.schedule_ui_callback(self.finish_refresh)
            return
        self.schedule_ui_callback(lambda: self.apply_usage(usage))
        self.schedule_ui_callback(self.finish_refresh)

    def schedule_refresh(self):
        self.refresh_async()
        self.root.after(REFRESH_SECONDS * 1000, self.schedule_refresh)

    def run(self):
        self.schedule_refresh()
        self.update_visibility()
        self.root.mainloop()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--reset-position", action="store_true", help="Center the widget and remember that position.")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    widget = UsageWidget()
    if args.reset_position:
        widget.reset_position()
    widget.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        message = (
            "Codex Usage Widget could not start.\n\n"
            f"{exc.__class__.__name__}: {exc}\n\n"
            "This usually means the selected Python install cannot load Tk/Tcl."
        )
        show_message_box = sys.platform == "win32" and not sys.stderr.isatty()
        if show_message_box:
            try:
                ctypes.windll.user32.MessageBoxW(0, message, "Codex Usage Widget", 0x10)
            except Exception:
                pass
        print(message, file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)
