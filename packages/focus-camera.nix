{ lib, stdenvNoCC, python3, wrapGAppsHook4, gobject-introspection, glib, gtk4, libcamera, gst_all_1 }:
let
  python = python3.withPackages (ps: [ ps.pygobject3 ps.numpy ]);
in stdenvNoCC.mkDerivation {
  pname = "erhai-focus-camera";
  version = "0.1";
  dontUnpack = true;
  nativeBuildInputs = [ wrapGAppsHook4 gobject-introspection ];
  buildInputs = [ glib gtk4 libcamera ] ++ (with gst_all_1; [
    gstreamer
    gst-plugins-base
    gst-plugins-good
    gst-plugins-rs
  ]);

  installPhase = ''
    runHook preInstall
    install -Dm755 ${./focus-camera/focus-camera.py} "$out/bin/erhai-focus-camera"
    substituteInPlace "$out/bin/erhai-focus-camera" \
      --replace-fail '#!/usr/bin/python3' '#!${python}/bin/python3'
    install -Dm644 ${./focus-camera/io.github.erhai.FocusCamera.desktop} \
      "$out/share/applications/io.github.erhai.FocusCamera.desktop"
    runHook postInstall
  '';

  meta = {
    description = "Rear camera preview and tap-to-focus for OnePlus Pad 2 Pro";
    license = lib.licenses.gpl2Only;
    mainProgram = "erhai-focus-camera";
  };
}
