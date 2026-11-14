#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Initialize OPD2413 Bluetooth automatically from its own factory NVRAM."""
# Adapted from ArmadaOS devices/oneplus-pad2pro/rootfs/overlay/
# usr/libexec/armada/opd2413-btaddr (MIT). See NOTICE.
import os
import argparse
from pathlib import Path
import re
import stat
import sys
import time
from bluetooth_factory import factory_address, soc_serial, store_address
from bluetooth_mgmt import Management, PUBLIC_ADDRESS

ADDRESS_FILE = Path('/var/lib/oneplus-pad2pro/bt-address')
COMPATIBLE = Path('/sys/firmware/devicetree/base/compatible')
BLUETOOTH = Path('/sys/class/bluetooth')


def read_address(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
            raise RuntimeError('address file must be a regular root-owned file without group/other writes')
        raw = os.read(fd, 64)
    finally:
        os.close(fd)
    address = raw.decode('ascii').strip().lower()
    if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', address):
        raise RuntimeError('invalid provisioned Bluetooth address')
    if address in ('00:00:00:00:00:00', 'ff:ff:ff:ff:ff:ff'):
        raise RuntimeError('empty/broadcast Bluetooth address is not a factory identity')
    return address


def target_index():
    matches = []
    for node in BLUETOOTH.glob('hci*'):
        if re.fullmatch(r'hci[0-9]+', node.name) and '898000.serial' in node.resolve().parts:
            matches.append(int(node.name[3:]))
    if len(matches) > 1:
        raise RuntimeError('multiple HCI controllers on the OPD2413 UART')
    return matches[0] if matches else None


def configure(desired, *, timeout=90):
    deadline = time.monotonic() + timeout
    applied = False
    with Management(deadline) as management:
        while time.monotonic() < deadline:
            index = target_index()
            if index is not None:
                current = management.info(index)
                if current:
                    if current != desired:
                        raise RuntimeError('configured controller identity differs from factory address')
                    print('opd2413-btaddr: factory identity verified on hci%d' % index)
                    return
                if not applied:
                    missing = management.missing_options(index)
                    if missing == PUBLIC_ADDRESS:
                        management.set_address(index, desired)
                        applied = True
                    elif missing:
                        raise RuntimeError('controller requires configuration beyond a public address')
            time.sleep(0.25)
    raise TimeoutError('timed out waiting for configured OPD2413 Bluetooth controller')


def provision(path):
    desired, copies, failures = factory_address(soc_serial())
    try:
        existing = read_address(path)
    except FileNotFoundError:
        try:
            store_address(path, desired)
        except FileExistsError:
            pass
        existing = read_address(path)
    if existing != desired:
        raise RuntimeError('stored Bluetooth identity differs from this tablet\'s factory identity')
    print('opd2413-btaddr: factory identity validated from ' + ', '.join(copies))
    for failure in failures:
        print('opd2413-btaddr: ignored invalid factory copy: ' + failure, file=sys.stderr)
    return desired


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-file', type=Path, default=ADDRESS_FILE,
                        help='persistent per-device address file')
    parser.add_argument('--check-factory', action='store_true',
                        help='validate factory copies without writing state or configuring HCI')
    args = parser.parse_args(argv)
    if not COMPATIBLE.exists() or b'oneplus,opd2413' not in COMPATIBLE.read_bytes().split(b'\0'):
        raise RuntimeError('not a OnePlus Pad 2 Pro (OPD2413)')
    if os.geteuid() != 0:
        raise RuntimeError('run as root on the tablet')
    if args.check_factory:
        _, copies, failures = factory_address(soc_serial())
        print('opd2413-btaddr: factory identity validated from ' + ', '.join(copies))
        for failure in failures:
            print('opd2413-btaddr: ignored invalid factory copy: ' + failure, file=sys.stderr)
        return
    configure(provision(args.state_file))


if __name__ == '__main__':
    try:
        main()
    except TimeoutError as exc:
        print('opd2413-btaddr: ' + str(exc), file=sys.stderr)
        sys.exit(75)  # EX_TEMPFAIL: firmware setup may still be retrying.
    except (OSError, ValueError, RuntimeError) as exc:
        print('opd2413-btaddr: ' + str(exc), file=sys.stderr)
        sys.exit(1)
