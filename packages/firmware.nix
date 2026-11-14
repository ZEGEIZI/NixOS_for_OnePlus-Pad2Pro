{ runCommand, python3, lib }:
let
  tools = builtins.path {
    path = ../tools;
    name = "tools";
    filter = path: _type:
      let name = builtins.baseNameOf path;
      in name != "__pycache__" && builtins.match ".*\\.py[co]" name == null;
  };
  archives = import ./firmware-archives.nix;
in runCommand "erhai-firmware-1" {
  nativeBuildInputs = [ python3 ];
  meta.license = lib.licenses.unfree;
} ''
  python3 ${tools}/stage-firmware.py ${archives.base} $out \
    --base-manifest ${../inputs/firmware/base.json} \
    --wifi-archive ${archives.wifi} \
    --wifi-manifest ${../inputs/firmware/wifi.json}
  cp ${../inputs/firmware/ORIGINAL-NOTICES.md} $out/share/doc/erhai-firmware/ORIGINAL-NOTICES.md
''
