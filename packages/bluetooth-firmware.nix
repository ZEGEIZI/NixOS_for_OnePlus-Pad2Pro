{ lib, runCommand, python3 }:
let
  archive = (import ./firmware-archives.nix).bluetooth;
in runCommand "opd2413-bluetooth-firmware-1" {
  nativeBuildInputs = [ python3 ];
  meta.license = lib.licenses.unfree;
} ''
  python3 ${../tools/bluetooth_firmware.py} stage ${archive} $out \
    --manifest ${../inputs/firmware/bluetooth.json}
  mkdir -p $out/share/doc/opd2413-bluetooth-firmware
  cp ${../inputs/firmware/bluetooth.json} \
    $out/share/doc/opd2413-bluetooth-firmware/manifest.json
''
