import json
import os
import re
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import codex_usage_widget as widget


class VersionContractTests(unittest.TestCase):
    def test_runtime_version_matches_project_metadata(self):
        metadata = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        version_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', metadata)

        self.assertIsNotNone(version_match)
        self.assertEqual(widget.APP_VERSION, version_match.group(1))

    def test_version_label_text_is_exact_and_derived_from_runtime_version(self):
        self.assertEqual(widget.VERSION_LABEL_TEXT, f"v {widget.APP_VERSION}")
        self.assertEqual(widget.VERSION_LABEL_TEXT, "v 1.0.0")


class StatePersistenceTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(os.environ.get("CODEX_USAGE_WIDGET_TEST_ROOT", Path(__file__).parent))
        self.temp_dir = tempfile.TemporaryDirectory(dir=temp_root)
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def test_source_runs_keep_state_beside_the_script(self):
        with patch.object(widget.sys, "frozen", False, create=True), patch.object(widget, "SOURCE_STATE_PATH", self.root / "legacy.json"):
            self.assertEqual(widget.state_path(), self.root / "legacy.json")

    def test_packaged_runs_use_local_app_data_and_migrate_legacy_state(self):
        executable = self.root / "CodexUsageWidget.exe"
        legacy_path = executable.with_name("codex_usage_widget_state.json")
        legacy_path.write_text(json.dumps({"x": 100}), encoding="utf-8")
        local_app_data = self.root / "local-app-data"

        with (
            patch.object(widget.sys, "frozen", True, create=True),
            patch.object(widget.sys, "executable", str(executable)),
            patch.dict("os.environ", {"LOCALAPPDATA": str(local_app_data)}, clear=False),
        ):
            self.assertEqual(widget.load_state(), {"x": 100})
            self.assertEqual(
                json.loads((local_app_data / "CodexUsageWidget" / "codex_usage_widget_state.json").read_text(encoding="utf-8")),
                {"x": 100},
            )

    def test_save_state_replaces_file_without_leaving_a_temporary_file(self):
        path = self.root / "nested" / "state.json"

        self.assertTrue(widget.save_state({"x": 10}, path))

        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"x": 10})
        self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_failed_atomic_replace_keeps_existing_state_and_cleans_up(self):
        path = self.root / "state.json"
        path.write_text(json.dumps({"x": 10}), encoding="utf-8")

        with (
            patch.object(widget.os, "replace", side_effect=OSError("disk unavailable")),
            patch.object(widget, "write_diagnostic"),
        ):
            self.assertFalse(widget.save_state({"x": 20}, path))

        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"x": 10})
        self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_saved_geometry_round_trips_through_state(self):
        path = self.root / "state.json"
        geometry = {"x": 40, "y": 50, "width": 286, "height": 129, "scale": 0.68}

        self.assertTrue(widget.save_state(geometry, path))

        self.assertEqual(widget.geometry_from_state(widget.load_state(path)), geometry)

    def test_missing_or_corrupt_state_falls_back_to_empty_state(self):
        path = self.root / "state.json"
        self.assertEqual(widget.load_state(path), {})
        path.write_text("not json", encoding="utf-8")
        with patch.object(widget, "write_diagnostic"):
            self.assertEqual(widget.load_state(path), {})

    def test_inaccessible_state_path_falls_back_to_empty_state(self):
        with (
            patch.object(Path, "exists", side_effect=OSError("access denied")),
            patch.object(widget, "write_diagnostic"),
        ):
            self.assertEqual(widget.load_state(self.root / "state.json"), {})

    def test_invalid_geometry_is_rejected_before_clamping(self):
        malformed = {"x": 10, "y": 20, "width": 286, "height": 129, "scale": "0.68"}

        self.assertIsNone(widget.geometry_from_state(malformed))
        self.assertIsNone(widget.clamp_geometry_to_work_area(malformed, (0, 0, 1920, 1080)))

    def test_non_positive_dimensions_and_invalid_scale_are_rejected(self):
        for key, value in (
            ("width", 0),
            ("height", -1),
            ("scale", float("nan")),
            ("scale", 1.1),
            ("scale", 10**1000),
        ):
            geometry = {"x": 10, "y": 20, "width": 286, "height": 129, "scale": 0.68}
            geometry[key] = value

            self.assertIsNone(widget.geometry_from_state(geometry))

    def test_diagnostics_use_state_directory_and_omit_exception_messages(self):
        state_path = self.root / "local-app-data" / "CodexUsageWidget" / "state.json"
        secret = "usage-token-and-payload"

        with patch.object(widget, "state_path", return_value=state_path):
            self.assertTrue(widget.write_diagnostic("refresh", RuntimeError(secret), (state_path,)))

        log_path = state_path.with_name(widget.DIAGNOSTIC_LOG_NAME)
        contents = log_path.read_text(encoding="utf-8")
        self.assertIn("RuntimeError", contents)
        self.assertIn(str(state_path), contents)
        self.assertNotIn(secret, contents)
        self.assertNotIn("usage-token", contents)

    def test_diagnostics_rotate_at_256_kb_with_one_backup(self):
        state_path = self.root / "CodexUsageWidget" / "state.json"
        log_path = state_path.with_name(widget.DIAGNOSTIC_LOG_NAME)
        log_path.parent.mkdir(parents=True)
        log_path.write_bytes(b"x" * widget.DIAGNOSTIC_MAX_BYTES)

        with patch.object(widget, "state_path", return_value=state_path):
            self.assertTrue(widget.write_diagnostic("startup", ValueError("do not record this"), (state_path,)))

        self.assertTrue(log_path.exists())
        self.assertTrue(log_path.with_name(f"{log_path.name}.1").exists())
        self.assertLessEqual(log_path.stat().st_size, widget.DIAGNOSTIC_MAX_BYTES)
        self.assertEqual(log_path.with_name(f"{log_path.name}.1").read_bytes(), b"x" * widget.DIAGNOSTIC_MAX_BYTES)


class SingleInstanceLockTests(unittest.TestCase):
    class FakeKernel32:
        def __init__(self, last_error=0, handle=1234):
            self.last_error = last_error
            self.handle = handle
            self.created = []
            self.released = []
            self.closed = []

        def CreateMutexW(self, security_attributes, initially_owned, name):
            self.created.append((security_attributes, initially_owned, name))
            return self.handle

        def GetLastError(self):
            return self.last_error

        def ReleaseMutex(self, handle):
            self.released.append(handle)
            return 1

        def CloseHandle(self, handle):
            self.closed.append(handle)
            return 1

    class SingleInstanceLockProbe:
        def __init__(self):
            self.releases = 0

        def release(self):
            self.releases += 1

    def test_first_instance_acquires_and_releases_named_mutex(self):
        kernel32 = self.FakeKernel32()

        with patch.object(widget, "kernel32", kernel32):
            instance_lock = widget.acquire_instance_lock()
            instance_lock.release()

        self.assertIsNotNone(instance_lock)
        self.assertEqual(kernel32.created, [(None, True, widget.INSTANCE_MUTEX_NAME)])
        self.assertEqual(kernel32.released, [kernel32.handle])
        self.assertEqual(kernel32.closed, [kernel32.handle])

    def test_second_instance_closes_existing_mutex_handle_and_exits_quietly(self):
        kernel32 = self.FakeKernel32(last_error=widget.ERROR_ALREADY_EXISTS, handle=5678)

        with patch.object(widget, "kernel32", kernel32):
            self.assertIsNone(widget.acquire_instance_lock())

        self.assertEqual(kernel32.released, [])
        self.assertEqual(kernel32.closed, [kernel32.handle])

    def test_main_returns_without_starting_a_second_instance(self):
        with (
            patch.object(widget, "acquire_instance_lock", return_value=None),
            patch.object(widget, "UsageWidget") as usage_widget,
        ):
            self.assertIsNone(widget.main([]))

        usage_widget.assert_not_called()

    def test_main_releases_lock_after_widget_closes(self):
        instance_lock = self.SingleInstanceLockProbe()

        class WidgetProbe:
            def run(self):
                return None

        with (
            patch.object(widget, "acquire_instance_lock", return_value=instance_lock),
            patch.object(widget, "UsageWidget", return_value=WidgetProbe()),
        ):
            widget.main([])

        self.assertEqual(instance_lock.releases, 1)

    def test_main_releases_lock_when_widget_startup_fails(self):
        instance_lock = self.SingleInstanceLockProbe()

        with (
            patch.object(widget, "acquire_instance_lock", return_value=instance_lock),
            patch.object(widget, "UsageWidget", side_effect=RuntimeError("Tk unavailable")),
        ):
            with self.assertRaisesRegex(RuntimeError, "Tk unavailable"):
                widget.main([])

        self.assertEqual(instance_lock.releases, 1)


class FocusDetectionTests(unittest.TestCase):
    def test_normal_codex_title_is_checked_before_the_process_path(self):
        with (
            patch.object(widget, "active_window_title", return_value="Codex — Project"),
            patch.object(widget, "active_process_path", side_effect=PermissionError("access denied")) as process_path,
        ):
            self.assertTrue(widget.codex_has_focus())

        process_path.assert_not_called()

    def test_store_codex_title_is_accepted_when_package_name_changes(self):
        with (
            patch.object(widget, "active_window_title", return_value="ChatGPT Codex"),
            patch.object(widget, "active_process_path", side_effect=PermissionError("access denied")) as process_path,
        ):
            self.assertTrue(widget.codex_has_focus())

        process_path.assert_not_called()

    def test_store_package_marker_is_a_fallback_when_title_is_unavailable(self):
        with (
            patch.object(widget, "active_window_title", return_value=""),
            patch.object(
                widget,
                "active_process_path",
                return_value=r"C:\WindowsApps\OpenAI.Codex_1.2.3\ChatGPT.exe",
            ),
        ):
            self.assertTrue(widget.codex_has_focus())

    def test_inaccessible_process_path_does_not_raise_for_an_unrelated_title(self):
        with (
            patch.object(widget, "active_window_title", return_value="Calculator"),
            patch.object(widget, "active_process_path", side_effect=PermissionError("access denied")),
        ):
            self.assertFalse(widget.codex_has_focus())

    def test_unrelated_title_is_rejected(self):
        with (
            patch.object(widget, "active_window_title", return_value="My Codex Notes"),
            patch.object(widget, "active_process_path", return_value="C:\\Windows\\explorer.exe"),
        ):
            self.assertFalse(widget.codex_has_focus())


class UsageNormalizationTests(unittest.TestCase):
    def test_utilization_is_shown_as_remaining_usage(self):
        usage = widget.normalize_usage(
            {
                "primary_window": {"pct": 25},
                "secondary_window": {"usage_percent": 75},
            }
        )

        self.assertEqual(usage["session_percent"], 75)
        self.assertEqual(usage["weekly_percent"], 25)

    def test_utilization_one_is_one_percent(self):
        usage = widget.normalize_usage(
            {
                "primary_window": {"pct": 1},
                "secondary_window": {"usage_percent": "1"},
            }
        )

        self.assertEqual(usage["session_percent"], 99)
        self.assertEqual(usage["weekly_percent"], 99)

    def test_explicit_fraction_values_are_converted_to_percentages(self):
        usage = widget.normalize_usage(
            {
                "primary_window": {"remaining_fraction": 0.25},
                "secondary_window": {"fraction_available": "0.375"},
            }
        )

        self.assertEqual(usage["session_percent"], 25)
        self.assertEqual(usage["weekly_percent"], 38)

    def test_malformed_usage_values_are_not_displayed_as_percentages(self):
        usage = widget.normalize_usage(
            {
                "primary_window": {"pct": "invalid"},
                "secondary_window": {"usage_percent": None},
            }
        )

        self.assertIsNone(usage["session_percent"])
        self.assertIsNone(usage["weekly_percent"])

    def test_out_of_range_usage_values_are_not_displayed_as_percentages(self):
        usage = widget.normalize_usage(
            {
                "primary_window": {"pct": 101},
                "secondary_window": {"fraction_remaining": 1.5},
            }
        )

        self.assertIsNone(usage["session_percent"])
        self.assertIsNone(usage["weekly_percent"])


class UsageLoadingTests(unittest.TestCase):
    def test_usage_command_prefers_path_before_uv_locations(self):
        with (
            patch.object(widget.sys, "platform", "win32"),
            patch.object(widget.shutil, "which", return_value="C:/path/codex-cli-usage.exe"),
        ):
            self.assertEqual(widget.find_usage_command(), "C:/path/codex-cli-usage.exe")

    def test_usage_command_finds_standard_windows_uv_tool_environment(self):
        temp_root = Path(os.environ.get("CODEX_USAGE_WIDGET_TEST_ROOT", Path(__file__).parent))
        with tempfile.TemporaryDirectory(dir=temp_root) as temp_dir:
            root = Path(temp_dir)
            command = (
                root
                / "AppData"
                / "Local"
                / "uv"
                / "tools"
                / "codex-cli-usage"
                / "Scripts"
                / "codex-cli-usage.exe"
            )
            command.parent.mkdir(parents=True)
            command.write_text("", encoding="utf-8")

            with (
                patch.object(widget.sys, "platform", "win32"),
                patch.object(widget.Path, "home", return_value=root),
                patch.dict(
                    "os.environ",
                    {
                        "APPDATA": str(root / "AppData" / "Roaming"),
                        "LOCALAPPDATA": str(root / "AppData" / "Local"),
                    },
                    clear=True,
                ),
                patch.object(widget.shutil, "which", return_value=None),
            ):
                self.assertEqual(widget.find_usage_command(), str(command))

    def test_usage_command_retries_once_after_timeout_with_ten_second_limit(self):
        command_result = widget.subprocess.CompletedProcess(
            args=["codex-cli-usage", "json"],
            returncode=0,
            stdout=json.dumps(
                {
                    "plan": "plus",
                    "5h": {"pct": 6},
                    "7d": {"pct": 3},
                }
            ),
            stderr="",
        )

        with (
            patch.object(widget, "find_usage_command", return_value="codex-cli-usage"),
            patch.object(
                widget.subprocess,
                "run",
                side_effect=[widget.subprocess.TimeoutExpired("codex-cli-usage", 10), command_result],
            ) as run,
            patch.object(widget.time, "sleep") as sleep,
        ):
            usage = widget.load_usage()

        self.assertEqual(usage["session_percent"], 94)
        self.assertEqual(usage["weekly_percent"], 97)
        self.assertEqual(run.call_count, 2)
        self.assertEqual([call.kwargs["timeout"] for call in run.call_args_list], [10, 10])
        sleep.assert_called_once_with(widget.REFRESH_RETRY_SECONDS)

    def test_usage_command_does_not_retry_more_than_once(self):
        timeout = widget.subprocess.TimeoutExpired("codex-cli-usage", 10)

        with (
            patch.object(widget, "find_usage_command", return_value="codex-cli-usage"),
            patch.object(widget.subprocess, "run", side_effect=[timeout, timeout]) as run,
            patch.object(widget.time, "sleep") as sleep,
        ):
            with self.assertRaises(widget.subprocess.TimeoutExpired):
                widget.load_usage()

        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(widget.REFRESH_RETRY_SECONDS)

    def test_usage_command_gets_usable_network_environment(self):
        command_result = widget.subprocess.CompletedProcess(
            args=["codex-cli-usage", "json"],
            returncode=0,
            stdout=json.dumps(
                {
                    "plan": "plus",
                    "5h": {"pct": 6, "resets_at": "2026-09-08T20:57:11+00:00"},
                    "7d": {"pct": 3, "resets_at": "2026-09-15T10:47:10+00:00"},
                }
            ),
            stderr="",
        )

        with (
            patch.dict(
                "os.environ",
                {
                    "HTTP_PROXY": "http://127.0.0.1:9",
                    "HTTPS_PROXY": "http://127.0.0.1:9",
                    "ALL_PROXY": "http://127.0.0.1:9",
                },
                clear=True,
            ),
            patch.object(socket, "create_connection", side_effect=OSError("connection refused")),
            patch.object(widget, "find_ssl_cert_file", return_value=Path(__file__)),
            patch.object(widget.shutil, "which", return_value="codex-cli-usage"),
            patch.object(widget.subprocess, "run", return_value=command_result) as run,
        ):
            usage = widget.load_usage()

        self.assertEqual(usage["session_percent"], 94)
        self.assertEqual(usage["weekly_percent"], 97)
        environment = run.call_args.kwargs["env"]
        self.assertNotIn("HTTP_PROXY", environment)
        self.assertNotIn("HTTPS_PROXY", environment)
        self.assertNotIn("ALL_PROXY", environment)
        self.assertEqual(environment["SSL_CERT_FILE"], str(Path(__file__)))


class RefreshShutdownTests(unittest.TestCase):
    def test_refresh_failure_writes_bounded_diagnostic(self):
        class FakeRoot:
            def after(self, _delay, _callback):
                return None

        usage_widget = widget.UsageWidget.__new__(widget.UsageWidget)
        usage_widget.root = FakeRoot()
        usage_widget.closing = False
        state_path = Path("C:/Users/example/AppData/Local/CodexUsageWidget/state.json")
        failure = RuntimeError("usage payload must not be logged")

        with (
            patch.object(widget, "load_usage", side_effect=failure),
            patch.object(widget, "state_path", return_value=state_path),
            patch.object(widget, "write_diagnostic") as write_diagnostic,
        ):
            usage_widget.refresh_worker()

        write_diagnostic.assert_called_once_with("refresh", failure, (state_path,))

    def test_late_ui_callback_is_ignored_after_widget_closes(self):
        class FakeRoot:
            def after(self, _delay, callback):
                self.callback = callback

        usage_widget = widget.UsageWidget.__new__(widget.UsageWidget)
        usage_widget.root = FakeRoot()
        usage_widget.closing = False
        calls = []

        self.assertTrue(usage_widget.schedule_ui_callback(lambda: calls.append("called")))
        usage_widget.closing = True
        usage_widget.root.callback()

        self.assertEqual(calls, [])

    def test_scheduling_after_tk_shutdown_is_ignored(self):
        class ClosedRoot:
            def after(self, _delay, _callback):
                raise RuntimeError("main thread is not in main loop")

        usage_widget = widget.UsageWidget.__new__(widget.UsageWidget)
        usage_widget.root = ClosedRoot()
        usage_widget.closing = False

        self.assertFalse(usage_widget.schedule_ui_callback(lambda: None))


if __name__ == "__main__":
    unittest.main()
