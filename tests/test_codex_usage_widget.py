import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import codex_usage_widget as widget


class StatePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
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

        with patch.object(widget.os, "replace", side_effect=OSError("disk unavailable")):
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
        self.assertEqual(widget.load_state(path), {})


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

    def test_malformed_usage_values_are_not_displayed_as_percentages(self):
        usage = widget.normalize_usage(
            {
                "primary_window": {"pct": "invalid"},
                "secondary_window": {"usage_percent": None},
            }
        )

        self.assertIsNone(usage["session_percent"])
        self.assertIsNone(usage["weekly_percent"])


class RefreshShutdownTests(unittest.TestCase):
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
