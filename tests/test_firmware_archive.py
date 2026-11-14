import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import firmware_archive as firmware


class BaseFirmware(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        (self.source / "qcom").mkdir(parents=True)
        (self.source / "qcom/adsp.mdt").write_bytes(b"firmware")
        self.manifest = self.root / "manifest.json"
        self.files = [{"install": "qcom/adsp.mdt", "size": 8,
                       "sha256": hashlib.sha256(b"firmware").hexdigest()}]
        self.manifest.write_text(json.dumps({"schema": 1, "files": self.files}))

    def test_repeatable_pack_and_source_integrity(self):
        one, two = self.root / "one.tar", self.root / "two.tar"
        self.assertEqual(firmware.pack(self.source, one, self.manifest),
                         firmware.pack(self.source, two, self.manifest))
        self.assertEqual(firmware.read_archive(one, self.manifest), {"qcom/adsp.mdt": b"firmware"})
        (self.source / "qcom/adsp.mdt").write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "Firmware mismatch"):
            firmware.pack(self.source, self.root / "bad.tar", self.manifest)
        self.assertFalse((self.root / "bad.tar").exists())

    def test_bad_archive_members_and_hashes(self):
        for kind in ("duplicate", "extra", "symlink", "corrupt"):
            with self.subTest(kind=kind):
                archive = self.root / (kind + ".tar")
                with tarfile.open(archive, "w") as bundle:
                    member = tarfile.TarInfo("qcom/adsp.mdt")
                    member.size = 8
                    if kind == "symlink":
                        member.type, member.linkname = tarfile.SYMTYPE, "/etc/shadow"
                        bundle.addfile(member)
                    else:
                        bundle.addfile(member, io.BytesIO(b"modified" if kind == "corrupt" else b"firmware"))
                    if kind in ("duplicate", "extra"):
                        bundle.addfile(tarfile.TarInfo("qcom/adsp.mdt" if kind == "duplicate" else "../escape"))
                with self.assertRaises(ValueError):
                    firmware.read_archive(archive, self.manifest)

    def test_unsafe_inventory_paths(self):
        for name in ("../escape", "/etc/shadow", "qcom/../escape", "qcom//adsp.mdt", "."):
            with self.subTest(name=name):
                self.files[0]["install"] = name
                self.manifest.write_text(json.dumps({"schema": 1, "files": self.files}))
                with self.assertRaises(ValueError):
                    firmware.inventory(self.manifest)
