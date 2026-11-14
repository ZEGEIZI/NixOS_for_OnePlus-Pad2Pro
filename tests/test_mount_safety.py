import contextlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
spec = importlib.util.spec_from_file_location("installer", Path(__file__).resolve().parents[1] / "tools/kshim-install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class MountSafety(unittest.TestCase):
    def setUp(self):
        guard = patch.object(installer.protocol, "locked", return_value=contextlib.nullcontext())
        guard.start()
        self.addCleanup(guard.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.boot = Path(self.temp.name)
        self.uuid = "00000000-0000-4000-8000-000000000001"
        self.args = SimpleNamespace(staging_root=None, boot_dir=self.boot,
                                    partuuid=self.uuid, partlabel="KShinC_BOOT")
        self.mount = {"target": str(self.boot), "source": "/dev/test", "fstype": "ext4",
                      "fsroot": "/", "partlabel": "KShinC_BOOT", "partuuid": self.uuid,
                      "options": "ro,noatime"}

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_uuid_never_remounts(self):
        self.args.partuuid = None
        with patch.object(installer.subprocess, "run") as run:
            with self.assertRaises(ValueError), installer.boot_mount(self.args):
                self.fail("must not yield")
            run.assert_not_called()

    def test_wrong_partition_or_subdirectory_never_remounts(self):
        for field, wrong in [("partuuid", "wrong"), ("fstype", "btrfs"),
                             ("partlabel", "ARMADA_BOOT"), ("fsroot", "/subdir")]:
            mount = dict(self.mount, **{field: wrong})
            with self.subTest(field=field), patch.object(installer.subprocess, "check_output",
                    return_value=json.dumps({"filesystems": [mount]})), patch.object(installer.subprocess, "run") as run:
                with self.assertRaises(ValueError), installer.boot_mount(self.args):
                    self.fail("must not yield")
                run.assert_not_called()

    def test_readonly_restored_on_failure(self):
        with patch.object(installer.subprocess, "check_output", return_value=json.dumps({"filesystems": [self.mount]})), \
                patch.object(installer.subprocess, "run") as run, \
                patch.object(installer.protocol, "root", return_value=self.boot), patch.object(installer.os, "sync") as sync:
            with self.assertRaisesRegex(RuntimeError, "publication failed"):
                with installer.boot_mount(self.args):
                    raise RuntimeError("publication failed")
            self.assertEqual([c.args[0] for c in run.call_args_list], [
                ["mount", "-o", "remount,rw", str(self.boot)],
                ["mount", "-o", "remount,ro", str(self.boot)],
            ])
            sync.assert_called_once()

    def test_global_lock_covers_mount_and_restore(self):
        events = []

        @contextlib.contextmanager
        def guard(path):
            self.assertEqual(path, Path("/run/lock/nixos-kshim.lock"))
            events.append("locked")
            yield
            events.append("unlocked")

        @contextlib.contextmanager
        def mounted(args):
            events.append("mounted")
            try:
                yield self.boot
            finally:
                events.append("restored")

        with patch.object(installer.protocol, "locked", side_effect=guard), \
                patch.object(installer, "mounted_boot", side_effect=mounted):
            with installer.boot_mount(self.args):
                events.append("writing")
        self.assertEqual(events, ["locked", "mounted", "writing", "restored", "unlocked"])
