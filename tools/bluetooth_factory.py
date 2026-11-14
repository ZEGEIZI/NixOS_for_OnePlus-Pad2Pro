# SPDX-License-Identifier: MIT
"""Read OPD2413's own Bluetooth identity from Oplus redundant factory NVRAM.

Format verified against OPD2413 Android 16's nvram_server/nvram_qmi and
Android's adapter address. This reads OEM record 0 only, never writes NVRAM,
and never exports its other factory data. See docs/BLUETOOTH.md.
"""
import hashlib
import os
from pathlib import Path
import re
import stat
import struct
import tempfile


UNIT_SIZE = 4096
HEADER_SIZE = 448
BT_OFFSET = 998
PUBLIC_ADDRESS_SIZE = 6
MAGIC = b'OEM~~OEM'


def key_material(serial):
    if not 0 < serial <= 0xffffffff:
        raise ValueError('invalid SoC serial number')
    # Vendor format: a 15-character uppercase hexadecimal number plus NUL,
    # SHA-256, followed by three even/odd byte permutations and rotations.
    material = hashlib.sha256(f'{serial:015X}\0'.encode('ascii')).digest()
    for _ in range(3):
        material = (bytes(((b << 2) | (b >> 6)) & 255 for b in material[::2])
                    + bytes(((b >> 2) | (b << 6)) & 255 for b in material[1::2]))
    return material


def decode_record(unit, serial):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    if len(unit) != UNIT_SIZE:
        raise ValueError('truncated factory record')
    magic, item, length, overhead, state = struct.unpack_from('<8s4I', unit)
    if magic != MAGIC or item != 0 or state != 2:
        raise ValueError('unsupported or incomplete factory record header')
    if (length < BT_OFFSET + PUBLIC_ADDRESS_SIZE
            or overhead != 64 + (-length % 16)
            or HEADER_SIZE + length + overhead > UNIT_SIZE):
        raise ValueError('invalid factory record bounds')
    material = key_material(serial)
    decoder = Cipher(algorithms.AES(material[:16]), modes.CBC(material[16:])).decryptor()
    plaintext = decoder.update(unit[HEADER_SIZE:HEADER_SIZE + length + overhead]) + decoder.finalize()
    payload = plaintext[64:64 + length]
    if plaintext[:32] != hashlib.sha256(unit[:HEADER_SIZE]).digest():
        raise ValueError('factory header checksum mismatch')
    if plaintext[32:64] != hashlib.sha256(payload).digest():
        raise ValueError('factory payload checksum mismatch')
    # nvram_qmi returns this field in the same least-significant-byte-first
    # order as HCI. Display/state files use the conventional reverse order.
    address = payload[BT_OFFSET:BT_OFFSET + PUBLIC_ADDRESS_SIZE][::-1]
    if address in (bytes(6), b'\xff' * 6):
        raise ValueError('factory Bluetooth address is empty or broadcast')
    return ':'.join(f'{octet:02x}' for octet in address)


def soc_serial(sysfs=Path('/sys')):
    for relative in ('devices/soc0/serial_number', 'bus/soc/devices/soc0/serial_number'):
        try:
            text = (sysfs / relative).read_text().strip()
        except FileNotFoundError:
            continue
        if not re.fullmatch(r'[0-9]{1,10}', text):
            raise ValueError('invalid socinfo serial number format')
        value = int(text, 10)
        if not 0 < value <= 0xffffffff:
            raise ValueError('invalid socinfo serial number')
        return value
    raise RuntimeError('SoC identity is unavailable; load socinfo before Bluetooth provisioning')


def read_unit(path):
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
    try:
        if not stat.S_ISBLK(os.fstat(fd).st_mode):
            raise ValueError('factory source must be a block device')
        return os.pread(fd, UNIT_SIZE, 0)
    finally:
        os.close(fd)


def factory_address(serial, partitions=Path('/dev/disk/by-partlabel')):
    valid = []
    failures = []
    for name in ('nonmodemst1', 'nonmodemst2'):
        try:
            valid.append((name, decode_record(read_unit(partitions / name), serial)))
        except (OSError, ValueError) as exc:
            failures.append(f'{name}: {exc}')
    if not valid:
        raise RuntimeError('no valid factory Bluetooth identity: ' + '; '.join(failures))
    if len({address for _, address in valid}) != 1:
        raise RuntimeError('factory NVRAM copies disagree on Bluetooth identity')
    return valid[0][1], [name for name, _ in valid], failures


def store_address(path, address):
    """Publish a complete root-only state file without replacing an existing one."""
    parent = path.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    meta = parent.lstat()
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
        raise RuntimeError('address directory must be root-owned and not writable by other users')
    fd, temporary = tempfile.mkstemp(prefix='.bt-address-', dir=parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write((address + '\n').encode('ascii'))
            output.flush()
            os.fsync(output.fileno())
        # link() provides exclusive, atomic publication. A concurrent creator
        # or an unexpected existing symlink must never be overwritten.
        os.link(temporary, path)
        directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.unlink(temporary)
