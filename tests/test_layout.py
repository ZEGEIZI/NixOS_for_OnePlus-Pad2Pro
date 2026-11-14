import importlib.util
from pathlib import Path
import struct
import unittest
import zlib

spec = importlib.util.spec_from_file_location("layout", Path(__file__).resolve().parents[1] / "tools/plan-layout.py")
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


class Layout(unittest.TestCase):
    def capture(self, labels=("userdata", "ARMADA_BOOT", "ARMADA_ROOT")):
        sector = 4096
        entries = bytearray(128 * 128)
        # Synthetic 512 GiB-sized disk; no device identity or actual GPT UUIDs.
        ranges = [(4096, 100000000), (100000001, 100262144), (100262145, 125829119)]
        for index, (name, (start, end)) in enumerate(zip(labels, ranges)):
            offset = index * 128
            entries[offset:offset + 16] = b"t" * 16
            struct.pack_into("<QQ", entries, offset + 32, start, end)
            raw = name.encode("utf-16-le")
            entries[offset + 56:offset + 56 + len(raw)] = raw
        header = bytearray(sector)
        header[:8] = b"EFI PART"
        struct.pack_into("<II", header, 8, 0x10000, 92)
        struct.pack_into("<QIII", header, 72, 2, 128, 128, zlib.crc32(entries))
        struct.pack_into("<I", header, 16, zlib.crc32(header[:92]))
        return bytes(sector) + header + entries

    def test_exact_sizes_and_shared_boundaries(self):
        result = layout.plan(self.capture(), 4096, 200)
        userdata, boot, root = result["proposed_tail"]
        self.assertEqual(boot["bytes"], 2**30)
        self.assertEqual(root["bytes"], 200 * 2**30)
        self.assertEqual(userdata["end_lba"] + 1, boot["start_lba"])
        self.assertEqual(boot["end_lba"] + 1, root["start_lba"])
        self.assertEqual(root["label"], "NixOS_Root")
        self.assertEqual(boot["label"], "KShinC_BOOT")
        self.assertTrue(result["android_userdata_recreation_required"])

    def test_unknown_layout_and_checksum_rejected(self):
        with self.assertRaises(ValueError):
            layout.plan(self.capture(("userdata", "important-data", "ARMADA_ROOT")), 4096, 200)
        broken = bytearray(self.capture())
        broken[-1] ^= 1
        with self.assertRaises(ValueError):
            layout.plan(broken, 4096, 200)
        with self.assertRaises(ValueError):
            layout.plan(self.capture(), 4096, 1000)
