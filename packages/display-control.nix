{ writeShellApplication, symlinkJoin, glib, systemd, util-linux, coreutils,
  callPackage, chromium }:
let
  patterns = callPackage ./hdr-test-patterns.nix { };
  cli = writeShellApplication {
    name = "pad2pro-display";
    runtimeInputs = [ glib systemd util-linux coreutils ];
    text = builtins.readFile ../tools/display-precision.sh;
  };
  check = writeShellApplication {
    name = "pad2pro-hdr-check";
    text = ''
      exec ${chromium}/bin/chromium \
        "file://${patterns}/share/pad2pro-display-tests/hdr-gray-check.html?video=file://${patterns}/share/pad2pro-display-tests/steps.webm"
    '';
  };
in symlinkJoin {
  name = "pad2pro-display-control";
  paths = [ cli check patterns ];
  meta.mainProgram = "pad2pro-display";
}
