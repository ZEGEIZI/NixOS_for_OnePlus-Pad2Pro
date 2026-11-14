{ stdenvNoCC, lib, makeWrapper, python3 }:
let
  python = python3.withPackages (ps: [ ps.cryptography ]);
in stdenvNoCC.mkDerivation {
  pname = "opd2413-bluetooth";
  version = "1";
  dontUnpack = true;
  nativeBuildInputs = [ makeWrapper ];
  installPhase = ''
    mkdir -p $out/libexec/opd2413 $out/bin
    cp ${../tools/bluetooth-address.py} $out/libexec/opd2413/bluetooth-address.py
    cp ${../tools/bluetooth_factory.py} $out/libexec/opd2413/bluetooth_factory.py
    cp ${../tools/bluetooth_mgmt.py} $out/libexec/opd2413/bluetooth_mgmt.py
    makeWrapper ${python}/bin/python3 $out/bin/opd2413-bluetooth-address \
      --add-flags "$out/libexec/opd2413/bluetooth-address.py"
  '';
  meta = {
    description = "OnePlus Pad 2 Pro factory Bluetooth identity initialization";
    license = lib.licenses.mit;
    platforms = lib.platforms.linux;
  };
}
