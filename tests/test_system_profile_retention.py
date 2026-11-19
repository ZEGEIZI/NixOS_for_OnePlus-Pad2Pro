import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "retention", Path(__file__).resolve().parents[1] / "modules/retain-system-generations.py")
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)


class SystemProfileRetention(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / "store-output"
        self.target.mkdir()
        self.profile = self.root / "system"
        for number in (2, 5, 7, 11, 15):
            (self.root / f"system-{number}-link").symlink_to(self.target)
        self.profile.symlink_to("system-15-link")

    def test_latest_three_include_current(self):
        self.assertEqual(retention.retention_plan(self.profile, 3),
                         {"current": 15, "retained": [7, 11, 15], "removed": [2, 5]})

    def test_rollback_still_retains_exactly_three_and_current(self):
        self.profile.unlink()
        self.profile.symlink_to("system-2-link")
        self.assertEqual(retention.retention_plan(self.profile, 3),
                         {"current": 2, "retained": [2, 11, 15], "removed": [5, 7]})

    def test_one_generation_always_retains_current(self):
        self.assertEqual(retention.retention_plan(self.profile, 1)["retained"], [15])

    def test_under_limit_removes_nothing(self):
        self.assertEqual(retention.retention_plan(self.profile, 10)["removed"], [])

    def test_missing_selected_generation_aborts(self):
        (self.root / "system-15-link").unlink()
        with self.assertRaises(ValueError):
            retention.retention_plan(self.profile, 3)

    def test_invalid_limit_aborts(self):
        with self.assertRaises(ValueError):
            retention.retention_plan(self.profile, 0)

    def test_unrelated_profile_is_untouched(self):
        (self.root / "user-99-link").symlink_to(self.target)
        self.assertEqual(retention.retention_plan(self.profile, 3)["retained"], [7, 11, 15])

    def test_non_symlink_generation_aborts(self):
        (self.root / "system-5-link").unlink()
        (self.root / "system-5-link").mkdir()
        with self.assertRaises(ValueError):
            retention.retention_plan(self.profile, 3)
