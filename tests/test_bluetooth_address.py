#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Factory identity integrity, provisioning and MGMT protocol regressions."""
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import bluetooth_factory as factory
import bluetooth_mgmt as mgmt
spec = importlib.util.spec_from_file_location('btaddr', ROOT / 'tools/bluetooth-address.py')
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)
SERIAL = 0x12345678
ADDR = '10:20:30:40:50:60'


def fixture(address=ADDR, *, bad_header_hash=False, bad_data_hash=False):
    payload = bytearray(3504)
    payload[998:1004] = bytes.fromhex(address.replace(':', ''))[::-1]
    header = struct.pack('<8s4I', b'OEM~~OEM', 0, len(payload), 64, 2).ljust(448, b'\0')
    h1 = hashlib.sha256(header).digest()
    h2 = hashlib.sha256(payload).digest()
    if bad_header_hash:
        h1 = bytes(32)
    if bad_data_hash:
        h2 = bytes(32)
    material = factory.key_material(SERIAL)
    encoder = Cipher(algorithms.AES(material[:16]), modes.CBC(material[16:])).encryptor()
    return (header + encoder.update(h1 + h2 + payload) + encoder.finalize()).ljust(4096, b'\0')


class FactoryTests(unittest.TestCase):
    def test_key_format_vector(self):
        self.assertEqual(factory.key_material(SERIAL).hex(),
                         '7c2dc8ce89ee81fec3cbbb36a6ec3dbc5c09c1502d29c7a39ccbe7cd1d65bebf')

    def test_factory_address_byte_order(self):
        self.assertEqual(factory.decode_record(fixture(), SERIAL), ADDR)

    def test_wrong_device_key_fails_integrity(self):
        with self.assertRaisesRegex(ValueError, 'header checksum'):
            factory.decode_record(fixture(), SERIAL + 1)

    def test_both_hashes_are_required(self):
        for kwargs, message in [({'bad_header_hash': True}, 'header checksum'),
                                ({'bad_data_hash': True}, 'payload checksum')]:
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, message):
                factory.decode_record(fixture(**kwargs), SERIAL)

    def test_header_bounds_and_format_fail_closed(self):
        original = fixture()
        variants = [original[:-1], b'NOTOEM!!' + original[8:]]
        for offset, value in [(8, 1), (12, 999), (12, 2**32-1), (16, 0), (16, 80), (20, 1)]:
            data = bytearray(original)
            struct.pack_into('<I', data, offset, value)
            variants.append(data)
        for data in variants:
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                factory.decode_record(data, SERIAL)

    def test_empty_address_fails_even_with_valid_checksums(self):
        for addr in ['00:00:00:00:00:00', 'ff:ff:ff:ff:ff:ff']:
            with self.assertRaisesRegex(ValueError, 'empty or broadcast'):
                factory.decode_record(fixture(addr), SERIAL)

    def test_redundant_copies(self):
        with patch.object(factory, 'read_unit', return_value=fixture()):
            addr, copies, failures = factory.factory_address(SERIAL)
        self.assertEqual((addr, copies, failures), (ADDR, ['nonmodemst1', 'nonmodemst2'], []))

    def test_one_corrupt_copy_uses_other_valid_copy(self):
        with patch.object(factory, 'read_unit', side_effect=[bytes(4096), fixture()]):
            addr, copies, failures = factory.factory_address(SERIAL)
        self.assertEqual((addr, copies), (ADDR, ['nonmodemst2']))
        self.assertEqual(len(failures), 1)

    def test_disagreeing_copies_are_never_guessed(self):
        with patch.object(factory, 'read_unit', side_effect=[fixture(), fixture('10:20:30:40:50:61')]):
            with self.assertRaisesRegex(RuntimeError, 'disagree'):
                factory.factory_address(SERIAL)

    def test_no_valid_copy_fails(self):
        with patch.object(factory, 'read_unit', side_effect=FileNotFoundError('missing')):
            with self.assertRaisesRegex(RuntimeError, 'no valid factory'):
                factory.factory_address(SERIAL)

    def test_standard_socinfo_decimal_serial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            node = root / 'devices/soc0/serial_number'
            node.parent.mkdir(parents=True)
            node.write_text(str(SERIAL) + '\n')
            self.assertEqual(factory.soc_serial(root), SERIAL)
            for text in ['0', '-1', str(2**32), '0x12345678', 'not-a-serial']:
                node.write_text(text)
                with self.assertRaises(ValueError):
                    factory.soc_serial(root)

    def test_publish_is_exclusive_and_root_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bt-address'
            meta = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=0)
            with patch.object(Path, 'lstat', return_value=meta):
                factory.store_address(path, ADDR)
                with self.assertRaises(FileExistsError):
                    factory.store_address(path, '10:20:30:40:50:61')
            self.assertEqual(path.read_text(), ADDR + '\n')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(list(path.parent.glob('.bt-address-*')), [])

    def test_publish_rejects_unsafe_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bt-address'
            for mode, uid in [(stat.S_IFLNK | 0o777, 0), (stat.S_IFDIR | 0o777, 0),
                              (stat.S_IFDIR | 0o700, 1000)]:
                with patch.object(Path, 'lstat', return_value=SimpleNamespace(st_mode=mode, st_uid=uid)):
                    with self.assertRaisesRegex(RuntimeError, 'root-owned'):
                        factory.store_address(path, ADDR)
            self.assertFalse(path.exists())


class ControllerTests(unittest.TestCase):
    def configure(self, addresses, *, missing=mgmt.PUBLIC_ADDRESS):
        client = MagicMock()
        client.info.side_effect = addresses
        client.missing_options.return_value = missing
        with patch.object(bt, 'target_index', return_value=7), patch.object(bt, 'Management') as cls, patch.object(bt.time, 'sleep'):
            cls.return_value.__enter__.return_value = client
            bt.configure(ADDR)
        return client

    def test_unconfigured_waits_for_real_readback(self):
        client = self.configure([None, None, ADDR])
        client.set_address.assert_called_once_with(7, ADDR)
        self.assertEqual(client.info.call_count, 3)

    def test_configured_is_idempotent(self):
        client = self.configure([ADDR])
        client.set_address.assert_not_called()
        client.missing_options.assert_not_called()

    def test_other_identity_is_never_changed(self):
        with self.assertRaisesRegex(RuntimeError, 'identity differs'):
            self.configure(['10:20:30:40:50:61'])

    def test_other_missing_options_are_not_ignored(self):
        with self.assertRaisesRegex(RuntimeError, 'beyond a public address'):
            self.configure([None], missing=3)

    def test_ack_without_readback_times_out(self):
        with patch.object(bt.time, 'monotonic', side_effect=[0, 0, 91]):
            with self.assertRaisesRegex(TimeoutError, 'timed out'):
                self.configure([None])

    def test_exact_board_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp) / 'compatible'
            node.write_bytes(b'oneplus,opd2413-other\0qcom,sm8750\0')
            with patch.object(bt, 'COMPATIBLE', node), patch.object(bt, 'provision') as provision:
                with self.assertRaisesRegex(RuntimeError, 'not a OnePlus'):
                    bt.main([])
                provision.assert_not_called()

    def test_target_uart_excludes_usb_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            classes = root / 'bluetooth'
            classes.mkdir()
            for name, parent in [('hci0', 'usb1'), ('hci7', '898000.serial')]:
                target = root / parent / name
                target.mkdir(parents=True)
                (classes / name).symlink_to(target)
            with patch.object(bt, 'BLUETOOTH', classes):
                self.assertEqual(bt.target_index(), 7)

    def test_existing_provisioned_address_must_match_factory(self):
        with patch.object(bt, 'soc_serial', return_value=SERIAL), patch.object(bt, 'factory_address', return_value=(ADDR, ['nonmodemst1'], [])), patch.object(bt, 'read_address', return_value='10:20:30:40:50:61'), patch.object(bt, 'store_address') as store:
            with self.assertRaisesRegex(RuntimeError, 'stored Bluetooth identity differs'):
                bt.provision(Path('/unused'))
            store.assert_not_called()

    def test_missing_state_is_provisioned_and_read_back(self):
        with patch.object(bt, 'soc_serial', return_value=SERIAL), patch.object(bt, 'factory_address', return_value=(ADDR, ['nonmodemst1'], [])), patch.object(bt, 'read_address', side_effect=[FileNotFoundError(), ADDR]), patch.object(bt, 'store_address') as store:
            path = Path('/unused')
            self.assertEqual(bt.provision(path), ADDR)
            store.assert_called_once_with(path, ADDR)

    def test_symlink_address_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'address'
            path.symlink_to('/dev/null')
            with self.assertRaises(OSError):
                bt.read_address(path)

    def test_address_content_and_owner_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'address'
            for text in [ADDR + '\n', '00:00:00:00:00:00', 'ff:ff:ff:ff:ff:ff', ADDR + '\nextra', ADDR * 4]:
                path.write_text(text)
                with patch.object(bt.os, 'fstat', return_value=SimpleNamespace(st_mode=0o100600, st_uid=0)):
                    if text == ADDR + '\n':
                        self.assertEqual(bt.read_address(path), ADDR)
                    else:
                        with self.assertRaises(RuntimeError):
                            bt.read_address(path)
            with patch.object(bt.os, 'fstat', return_value=SimpleNamespace(st_mode=0o100600, st_uid=1000)):
                with self.assertRaisesRegex(RuntimeError, 'root-owned'):
                    bt.read_address(path)


class ManagementTests(unittest.TestCase):
    def event(self, index, opcode, *, status=0, data=b'', event=1):
        body = struct.pack('<HB', opcode, status) + data
        return struct.pack('<HHH', event, index, len(body)) + body

    def client(self):
        client = object.__new__(mgmt.Management)
        client.socket = MagicMock()
        client.deadline = float('inf')
        return client

    def test_ignores_other_controller_opcode_and_unsolicited_event(self):
        client = self.client()
        reply = self.event(7, mgmt.READ_INFO, data=b'payload')
        client.socket.recv.side_effect = [self.event(8, mgmt.READ_INFO), self.event(7, mgmt.READ_CONFIG_INFO), struct.pack('<HHH', 4, 7, 0), reply]
        self.assertEqual(client.call(mgmt.READ_INFO, 7), (0, b'payload'))
        self.assertEqual(client.socket.send.call_args.args[0], struct.pack('<HHH', 4, 7, 0))

    def test_rejection_status_is_propagated(self):
        client = self.client()
        client.socket.recv.return_value = self.event(7, mgmt.SET_PUBLIC_ADDRESS, status=0x0b, event=2)
        with self.assertRaisesRegex(RuntimeError, 'status 0x0b'):
            client.set_address(7, ADDR)

    def test_address_wire_order(self):
        client = self.client()
        client.socket.recv.return_value = self.event(7, mgmt.SET_PUBLIC_ADDRESS)
        client.set_address(7, ADDR)
        self.assertEqual(client.socket.send.call_args.args[0], bytes.fromhex('390007000600605040302010'))

    def test_malformed_events_fail(self):
        for packet in [b'', struct.pack('<HHH', 1, 7, 100), struct.pack('<HHH', 1, 7, 0)]:
            client = self.client()
            client.socket.recv.return_value = packet
            with self.assertRaises(RuntimeError):
                client.call(mgmt.READ_INFO, 7)

    def test_info_and_configuration_layout(self):
        client = self.client()
        with patch.object(client, 'call', return_value=(0, bytes.fromhex('605040302010') + bytes(11))):
            self.assertEqual(client.info(7), ADDR)
        with patch.object(client, 'call', return_value=(0, struct.pack('<HII', 29, 2, 2))):
            self.assertEqual(client.missing_options(7), mgmt.PUBLIC_ADDRESS)
        with patch.object(client, 'call', return_value=(0, b'bad')):
            with self.assertRaises(RuntimeError):
                client.info(7)
            with self.assertRaises(RuntimeError):
                client.missing_options(7)


if __name__ == '__main__':
    unittest.main()
