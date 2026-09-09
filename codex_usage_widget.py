import argparse
import importlib.util
import json
import logging
import math
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import ctypes
import traceback
from ctypes import wintypes
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from re import match
from tkinter import BOTH, NW, Button, Canvas, Label, TclError, Tk
from urllib.parse import urlsplit


REFRESH_SECONDS = 5 * 60
REFRESH_RETRY_SECONDS = 3
VISIBILITY_CHECK_MS = 250
APP_VERSION = "1.0.0"
VERSION_LABEL_TEXT = f"v {APP_VERSION}"
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
DIAGNOSTIC_LOG_NAME = "codex_usage_widget.log"
DIAGNOSTIC_MAX_BYTES = 256 * 1024
DIAGNOSTIC_BACKUP_COUNT = 1
CREATE_NO_WINDOW = 0x08000000
PROXY_ENV_NAMES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
USAGE_TIMEOUT_SECONDS = 10
USAGE_MAX_ATTEMPTS = 2
USAGE_COMMAND_NAME = "codex-cli-usage"
INSTANCE_MUTEX_NAME = r"Local\CodexUsageWidget"
ERROR_ALREADY_EXISTS = 183
DIAGNOSTIC_LOCK = threading.Lock()


user32 = ctypes.windll.user32 if sys.platform == "win32" else None
kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MONITOR_DEFAULTTONEAREST = 2
SPI_GETWORKAREA = 0x0030
SM_CXSCREEN = 0
SM_CYSCREEN = 1


if kernel32 is not None:
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.GetLastError.restype = wintypes.DWORD
    kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel32.ReleaseMutex.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL


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


class SingleInstanceLock:
    def __init__(self, handle=None):
        self.handle = handle

    def release(self):
        if self.handle is None or kernel32 is None:
            return

        handle = self.handle
        self.handle = None
        try:
            kernel32.ReleaseMutex(handle)
        finally:
            kernel32.CloseHandle(handle)


def acquire_instance_lock():
    if kernel32 is None:
        return SingleInstanceLock()

    handle = kernel32.CreateMutexW(None, True, INSTANCE_MUTEX_NAME)
    if not handle:
        error_code = kernel32.GetLastError()
        raise ctypes.WinError(error_code)

    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return None

    return SingleInstanceLock(handle)


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

    try:
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value)
    except OSError:
        return ""
    if not handle:
        return ""

    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
    except OSError:
        return ""
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
    title = (active_window_title() or "").strip().lower()
    if any(match(pattern, title) for pattern in CODEX_WINDOW_TITLE_PATTERNS):
        return True

    try:
        process_path = (active_process_path() or "").lower()
    except OSError:
        return False

    process_name = Path(process_path).name
    if process_name == "codex.exe":
        return True
    return process_name == "chatgpt.exe" and CODEX_PACKAGE_MARKER in process_path


def state_path():
    if not getattr(sys, "frozen", False):
        return legacy_state_path()
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local_app_data / APP_STATE_DIRECTORY / STATE_FILE_NAME


def legacy_state_path():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).with_name(STATE_FILE_NAME)
    return SOURCE_STATE_PATH


def diagnostic_log_path():
    return state_path().with_name(DIAGNOSTIC_LOG_NAME)


def write_diagnostic(phase, exc, paths=()):
    """Write bounded diagnostics without copying exception messages or payloads."""
    try:
        path = diagnostic_log_path()
        safe_paths = [str(item) for item in paths if item is not None]
        details = [phase, exc.__class__.__name__]
        details.extend(f"path={item}" for item in safe_paths)
        logger = logging.getLogger("codex_usage_widget.diagnostic")
        logger.setLevel(logging.ERROR)
        logger.propagate = False

        with DIAGNOSTIC_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                path,
                maxBytes=DIAGNOSTIC_MAX_BYTES,
                backupCount=DIAGNOSTIC_BACKUP_COUNT,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z"))
            logger.addHandler(handler)
            try:
                logger.error(" | ".join(details))
            finally:
                logger.removeHandler(handler)
                handler.close()
        return True
    except Exception:
        return False


def read_state(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        write_diagnostic("state", exc, (path,))
        return {}


def load_state(path=None):
    path = path or state_path()
    legacy_path = legacy_state_path()
    try:
        path_exists = path.exists()
        legacy_exists = legacy_path.exists()
    except OSError as exc:
        write_diagnostic("state", exc, (path, legacy_path))
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
    except OSError as exc:
        write_diagnostic("state", exc, (path,))
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
    if not all(key in state for key in keys):
        return None

    geometry = {key: state.get(key) for key in keys}
    coordinates_and_size = (geometry["x"], geometry["y"], geometry["width"], geometry["height"])
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in coordinates_and_size):
        return None
    if geometry["width"] <= 0 or geometry["height"] <= 0:
        return None

    scale = geometry["scale"]
    if isinstance(scale, bool) or not isinstance(scale, (int, float)):
        return None
    try:
        scale_is_valid = math.isfinite(scale) and MIN_SCALE <= scale <= MAX_SCALE
    except (OverflowError, TypeError):
        return None
    if not scale_is_valid:
        return None
    return geometry


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
    geometry = geometry_from_state(geometry)
    if geometry is None:
        return None

    x = geometry.get("x")
    y = geometry.get("y")
    width = geometry.get("width")
    height = geometry.get("height")
    scale = geometry.get("scale")

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


def parse_percent(value, *, fraction=False):
    if value is None or isinstance(value, bool):
        return None

    has_percent_suffix = False
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        has_percent_suffix = cleaned.endswith("%")
        if has_percent_suffix:
            cleaned = cleaned[:-1].strip()
        try:
            value = float(cleaned)
        except ValueError:
            return None
    elif isinstance(value, (int, float)):
        value = float(value)
    else:
        return None

    if not math.isfinite(value):
        return None
    if fraction and not has_percent_suffix:
        if not 0 <= value <= 1:
            return None
        value *= 100
    elif not 0 <= value <= 100:
        return None
    return int(round(value))


def parse_remaining(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1:
        return parse_percent(value, fraction=True)
    if isinstance(value, str) and "%" not in value:
        try:
            numeric_value = float(value.strip())
        except ValueError:
            numeric_value = None
        if numeric_value is not None and 0 <= numeric_value <= 1:
            return parse_percent(numeric_value, fraction=True)
    return parse_percent(value)


def find_percent(value):
    if isinstance(value, dict):
        used = parse_percent(value.get("pct"))
        if used is not None:
            return 100 - used
        for key in (
            "percent_remaining",
            "remaining_percent",
            "remaining_pct",
            "percent_available",
            "available_percent",
        ):
            percent = parse_percent(value.get(key))
            if percent is not None:
                return percent
        for key in (
            "fraction_remaining",
            "remaining_fraction",
            "fraction_available",
            "available_fraction",
        ):
            percent = parse_percent(value.get(key), fraction=True)
            if percent is not None:
                return percent
        for key in ("remaining", "available"):
            percent = parse_remaining(value.get(key))
            if percent is not None:
                return percent
        for key in ("used_percent", "usage_percent"):
            used = parse_percent(value.get(key))
            if used is not None:
                return 100 - used
    return parse_percent(value)


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


def unavailable_local_proxy(value):
    if not value:
        return False

    try:
        parsed = urlsplit(value if "://" in value else f"//{value}")
        hostname = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return False

    if hostname not in {"localhost", "127.0.0.1", "::1"}:
        return False

    try:
        with socket.create_connection((hostname, port), timeout=0.25):
            return False
    except OSError:
        return True


def find_ssl_cert_file():
    configured = os.environ.get("SSL_CERT_FILE")
    if configured:
        try:
            if Path(configured).is_file():
                return Path(configured)
        except OSError:
            pass

    candidates = []
    try:
        certifi = importlib.util.find_spec("certifi")
    except (ImportError, ValueError):
        certifi = None
    if certifi and certifi.origin:
        candidates.append(Path(certifi.origin).with_name("cacert.pem"))

    for prefix in (sys.prefix, sys.base_prefix):
        candidates.append(Path(prefix) / "Lib" / "site-packages" / "certifi" / "cacert.pem")

    for executable_name in ("python.exe", "pythonw.exe"):
        executable = shutil.which(executable_name)
        if executable:
            candidates.append(Path(executable).parent / "Lib" / "site-packages" / "certifi" / "cacert.pem")

    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def usage_process_environment():
    environment = os.environ.copy()
    for name in PROXY_ENV_NAMES:
        if unavailable_local_proxy(environment.get(name)):
            environment.pop(name, None)

    cert_file = find_ssl_cert_file()
    if cert_file:
        environment["SSL_CERT_FILE"] = str(cert_file)
    return environment


def find_usage_command():
    command = shutil.which(USAGE_COMMAND_NAME)
    if command or sys.platform != "win32":
        return command

    home = Path.home()
    app_data = Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
    local_app_data = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
    candidates = []
    configured_bin = os.environ.get("UV_TOOL_BIN_DIR")
    if configured_bin:
        candidates.append(Path(configured_bin) / f"{USAGE_COMMAND_NAME}.exe")

    configured_tool_dir = os.environ.get("UV_TOOL_DIR")
    if configured_tool_dir:
        candidates.append(Path(configured_tool_dir) / USAGE_COMMAND_NAME / "Scripts" / f"{USAGE_COMMAND_NAME}.exe")

    # uv's default executable directory is ~/.local/bin. Older uv releases and
    # custom data-directory settings can leave the tool environment in one of
    # these Windows data locations instead.
    candidates.extend(
        (
            home / ".local" / "bin" / f"{USAGE_COMMAND_NAME}.exe",
            app_data / "uv" / "data" / "tools" / USAGE_COMMAND_NAME / "Scripts" / f"{USAGE_COMMAND_NAME}.exe",
            local_app_data / "uv" / "data" / "tools" / USAGE_COMMAND_NAME / "Scripts" / f"{USAGE_COMMAND_NAME}.exe",
            app_data / "uv" / "tools" / USAGE_COMMAND_NAME / "Scripts" / f"{USAGE_COMMAND_NAME}.exe",
            local_app_data / "uv" / "tools" / USAGE_COMMAND_NAME / "Scripts" / f"{USAGE_COMMAND_NAME}.exe",
        )
    )

    seen = set()
    for candidate in candidates:
        key = os.path.normcase(str(candidate))
        if key in seen:
            continue
        seen.add(key)
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return None


def load_usage():
    command = find_usage_command()

    if command:
        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = CREATE_NO_WINDOW

        last_error = None
        for attempt in range(USAGE_MAX_ATTEMPTS):
            try:
                result = subprocess.run(
                    [command, "json"],
                    capture_output=True,
                    text=True,
                    timeout=USAGE_TIMEOUT_SECONDS,
                    check=True,
                    env=usage_process_environment(),
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
        self.version_label = Label(
            self.root,
            text=VERSION_LABEL_TEXT,
            bg=PANEL,
            fg=MUTED,
            font=self.font(8),
            anchor="e",
        )
        self.canvas.create_window(
            self.width - self.s(44),
            self.s(22),
            window=self.version_label,
            anchor="ne",
        )
        self.drag_handles.append(self.version_label)
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
            write_diagnostic("refresh", exc, (state_path(),))
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
    instance_lock = acquire_instance_lock()
    if instance_lock is None:
        return

    try:
        args = parse_args(argv)
        widget = UsageWidget()
        if args.reset_position:
            widget.reset_position()
        widget.run()
    finally:
        instance_lock.release()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        write_diagnostic("startup", exc, (Path(__file__), state_path()))
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
