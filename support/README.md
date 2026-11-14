# OPD2413 Bluetooth identity support

The same initialization program can be packaged by NixOS, Debian/Ubuntu, Fedora,
Arch or another Linux distribution. It reads the tablet's own original Bluetooth
address from redundant Oplus factory NVRAM, validates it, and configures the
onboard controller through the standard Linux Bluetooth MGMT socket.

Requirements:

- OnePlus Pad 2 Pro / OPD2413, identified by the exact `oneplus,opd2413` DT token.
- Working WCN7860 driver, UART, power sequencing and matching firmware.
- `CONFIG_QCOM_SOCINFO` and its `socinfo` module (or built-in equivalent), exposing
  the decimal SoC serial at `/sys/devices/soc0/serial_number`.
- Readable `nonmodemst1` and `nonmodemst2` GPT partitions and udev partlabel links.
- Python 3, the Python `cryptography` package, and root for block-device/MGMT access.

Install the programs and systemd integration as root from the repository root:

```sh
install -d -m 0755 /usr/libexec/opd2413
install -m 0644 tools/bluetooth-address.py tools/bluetooth_factory.py \
  tools/bluetooth_mgmt.py /usr/libexec/opd2413/
install -m 0644 support/opd2413-bluetooth-address.service /usr/lib/systemd/system/
install -m 0644 support/opd2413-bluetooth.conf /usr/lib/modules-load.d/
modprobe socinfo
python3 /usr/libexec/opd2413/bluetooth-address.py --check-factory
systemctl daemon-reload
systemctl enable opd2413-bluetooth-address.service
systemctl start opd2413-bluetooth-address.service
```

The service is pulled in before `bluetooth.service`. Power remains controlled by
BlueZ and the desktop. No `btmgmt` process, Android runtime, vendor daemon, Nix
installation, proprietary userspace binary or pre-seeded address is required.
NixOS uses the same three files with its own dependency and unit packaging.

Never include `/var/lib/oneplus-pad2pro/bt-address` in a generic image. The helper
creates this file exclusively and atomically with mode 0600, and verifies existing
state against the current tablet's factory identity. Do not erase the factory
partitions or replace their contents with another unit's data.

The decoder currently supports the OPD2413 record format verified on the test
unit's Android 16 installation. It reads only record 0, checks bounds and both
SHA-256 checksums, and rejects conflicting valid copies. It never modifies the
factory partitions. Unsupported layouts fail explicitly; they do not result in a
random address or an identity guessed by scanning raw storage.

See [the hardware investigation and validation scope](../docs/BLUETOOTH.md).
The [validation record](../docs/BLUETOOTH-VALIDATION.json) pins the tested helper
source hashes and deployed closure, and records the successful empty-cache
reboot. It contains no per-device address, serial, factory payload or pairing key.
