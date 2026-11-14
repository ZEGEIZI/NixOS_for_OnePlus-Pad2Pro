{ lib }:
pkg: builtins.elem (lib.getName pkg) [
  "erhai-firmware" "opd2413-bluetooth-firmware"
]
