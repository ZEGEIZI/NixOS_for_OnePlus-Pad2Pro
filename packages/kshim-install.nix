{ stdenvNoCC, python3, makeWrapper, util-linux, dtc, nix, coreutils }:
let
  vendor = builtins.path {
    path = ../inputs/kshim-protocol;
    name = "kshim-protocol";
    filter = path: _type:
      let name = builtins.baseNameOf path;
      in name != "__pycache__" && builtins.match ".*\\.py[co]" name == null;
  };
in
stdenvNoCC.mkDerivation {
  pname = "nixos-kshim-install";
  version = "0.1.0";
  meta.description = "kShimC boot entry installer for NixOS";
  dontUnpack = true;
  nativeBuildInputs = [ makeWrapper ];
  installPhase = ''
    mkdir -p $out/libexec $out/bin
    cp ${../tools/kshim-install.py} $out/libexec/kshim-install.py
    cp ${../tools/kshim-cleanup.py} $out/libexec/kshim-cleanup.py
    cp ${../tools/kshim_protocol.py} $out/libexec/kshim_protocol.py
    mkdir -p $out/inputs
    cp -r ${vendor} $out/inputs/kshim-protocol
    # nixos-install runs as root with a writable store; never create .pyc there.
    makeWrapper ${python3}/bin/python3 $out/bin/nixos-kshim-install \
      --add-flags "-B $out/libexec/kshim-install.py" \
      --prefix PATH : ${util-linux}/bin:${dtc}/bin:${nix}/bin:${coreutils}/bin
    makeWrapper ${python3}/bin/python3 $out/bin/nixos-kshim-prune \
      --add-flags "-B $out/libexec/kshim-cleanup.py" \
      --prefix PATH : ${util-linux}/bin:${dtc}/bin:${nix}/bin:${coreutils}/bin
  '';
}
