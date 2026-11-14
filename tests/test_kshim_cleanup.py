import importlib.util
import os
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import test_boot_pruning as fixtures

spec = importlib.util.spec_from_file_location("cleanup", Path(__file__).resolve().parents[1] / "tools/kshim-cleanup.py")
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


class AutomaticCleanup(unittest.TestCase):
    def setUp(self):
        fixtures.BootPruning.setUp(self)
        self.profiles = self.base / "profiles"
        self.runtime = self.base / "run"
        self.profiles.mkdir()
        self.runtime.mkdir()
        for number in (2, 3, 4):
            (self.profiles / f"system-{number}-link").symlink_to(self.expected[f"nixos-v{number}"])
        (self.profiles / "system").symlink_to(self.expected["nixos-v4"])
        (self.runtime / "current-system").symlink_to(self.expected["nixos-v4"])
        (self.runtime / "booted-system").symlink_to(self.expected["nixos-v4"])
        self.auto = SimpleNamespace(
            staging_root=self.boot, profiles_dir=self.profiles, runtime_dir=self.runtime,
            state_dir=self.base / "state", configuration_limit=10, keep_previous=True,
            keep_version=[], dry_run=False)
        # Fixture manifests use unrealised store paths; exercise the same
        # state algorithm without requiring a real /nix/store in unit tests.
        links = patch.object(cleanup, "system_link", side_effect=lambda p: os.readlink(p))
        links.start()
        self.addCleanup(links.stop)

    def run_auto(self):
        return cleanup.cleanup(self.auto)

    def tearDown(self):
        fixtures.BootPruning.tearDown(self)

    def test_profile_deletion_updates_menu_and_roots(self):
        (self.profiles / "system-2-link").unlink()
        result = self.run_auto()
        self.assertEqual(result["removed"], ["nixos-v1", "nixos-v2"])
        self.assertEqual(result["retained"], ["nixos-v4", "nixos-v3"])
        self.assertEqual(len(list(self.profiles.glob("system-*-link"))), 2)
        self.assertEqual(len(list((self.boot / ".nixos-gcroots").iterdir())), 2)
        self.assertEqual(self.run_auto()["removed"], [])

    def test_different_booted_activated_and_profile_are_protected(self):
        for path in self.profiles.glob("system-*-link"):
            path.unlink()
        (self.runtime / "booted-system").unlink()
        (self.runtime / "booted-system").symlink_to(self.expected["nixos-v1"])
        (self.runtime / "current-system").unlink()
        (self.runtime / "current-system").symlink_to(self.expected["nixos-v2"])
        self.assertEqual(self.run_auto()["removed"], [])

    def test_limit_keeps_most_recent_profiles_and_previous(self):
        self.auto.configuration_limit = 1
        self.assertEqual(self.run_auto()["removed"], ["nixos-v1", "nixos-v2"])

    def test_zero_limit_means_all_remaining_profiles(self):
        self.auto.configuration_limit = 0
        self.assertEqual(self.run_auto()["removed"], ["nixos-v1"])

    def test_explicit_default_and_pin_survive_deleted_profiles(self):
        self.auto.configuration_limit = 1
        self.auto.keep_version = ["nixos-v1"]
        self.config.write_text("format=1\nsystems=nixos\ndefault=nixos/nixos-v2\ntimeout_ms=8000\n")
        self.assertEqual(self.run_auto()["removed"], [])

    def test_missing_pin_aborts_before_changes(self):
        self.auto.keep_version = ["missing"]
        before = (self.system / "entries.conf").read_bytes()
        with self.assertRaisesRegex(ValueError, "Pinned"):
            self.run_auto()
        self.assertEqual((self.system / "entries.conf").read_bytes(), before)

    def test_disable_previous_retention(self):
        self.auto.keep_previous = False
        self.auto.configuration_limit = 1
        result = self.run_auto()
        self.assertEqual(result["retained"], ["nixos-v4"])
        self.assertEqual(result["previous"], "none")

    def test_previous_alias_default_is_protected(self):
        self.auto.keep_previous = False
        self.auto.configuration_limit = 1
        self.config.write_text("format=1\nsystems=nixos\ndefault=nixos/previous\ntimeout_ms=8000\n")
        self.assertEqual(self.run_auto()["retained"], ["nixos-v4", "nixos-v3"])

    def test_dry_run_does_not_change_files_or_roots(self):
        self.auto.dry_run = True
        before = (self.system / "entries.conf").read_bytes()
        self.assertEqual(self.run_auto()["removed"], ["nixos-v1"])
        self.assertEqual((self.system / "entries.conf").read_bytes(), before)
        self.assertEqual(len(list((self.boot / ".nixos-gcroots").iterdir())), 4)
        self.assertFalse(self.auto.state_dir.exists())

    def test_corrupt_payload_or_symlink_prevents_deletion(self):
        (self.system / "versions/nixos-v1/Image").unlink()
        (self.system / "versions/nixos-v1/Image").symlink_to(self.base / "Image")
        with self.assertRaises(ValueError):
            self.run_auto()
        self.assertEqual(len(list((self.boot / ".nixos-gcroots").iterdir())), 4)

    def test_profile_change_aborts_before_menu_publication(self):
        before = (self.system / "entries.conf").read_bytes()
        state = cleanup.snapshot(self.profiles, self.runtime)
        with patch.object(cleanup, "snapshot", side_effect=[state, {}]):
            with self.assertRaisesRegex(ValueError, "changed"):
                self.run_auto()
        self.assertEqual((self.system / "entries.conf").read_bytes(), before)

    def test_interrupted_payload_deletion_is_retryable(self):
        with patch.object(cleanup.shutil, "rmtree", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.run_auto()
        self.assertNotIn("nixos-v1", cleanup.protocol.versions(self.system)["versions"])
        self.assertTrue((self.boot / ".nixos-gcroots/nixos-v1").is_symlink())
        self.assertEqual(self.run_auto()["removed"], ["nixos-v1"])

    def test_interrupted_root_deletion_is_retryable(self):
        # Reproduce payload removal succeeding before its GC root unlink.
        cleanup.protocol.write_versions(self.system, "nixos-v4", "nixos-v3",
                                        ["nixos-v4", "nixos-v3", "nixos-v2"])
        cleanup.shutil.rmtree(self.system / "versions/nixos-v1")
        self.assertEqual(self.run_auto()["orphan_roots_removed"], ["nixos-v1"])
        self.assertFalse((self.boot / ".nixos-gcroots/nixos-v1").is_symlink())

    def test_partially_removed_unlisted_payload_is_retryable(self):
        cleanup.protocol.write_versions(self.system, "nixos-v4", "nixos-v3",
                                        ["nixos-v4", "nixos-v3", "nixos-v2"])
        (self.system / "versions/nixos-v1/manifest.conf").unlink()
        self.assertEqual(self.run_auto()["removed"], ["nixos-v1"])

    def test_referenced_orphan_is_verified_and_restored(self):
        cleanup.protocol.write_versions(self.system, "nixos-v4", "nixos-v3",
                                        ["nixos-v4", "nixos-v3", "nixos-v2"])
        (self.runtime / "booted-system").unlink()
        (self.runtime / "booted-system").symlink_to(self.expected["nixos-v1"])
        result = self.run_auto()
        self.assertIn("nixos-v1", result["retained"])
        self.assertEqual(cleanup.protocol.versions(self.system)["versions"], result["retained"])
