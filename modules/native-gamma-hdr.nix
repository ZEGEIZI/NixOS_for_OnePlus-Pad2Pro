{ config, lib, pkgs, ... }:
let
  outputFrc = config.hardware.oneplus-pad2pro.experimentalOutputFrc;
in {
  imports = [ ./chromium-hdr.nix ];

  options.hardware.oneplus-pad2pro.experimentalOutputFrc =
    lib.mkEnableOption "12-bit equivalent dithering as the default HDR precision (10-bit remains available)";

  config = {
    nixpkgs.overlays = [
      (_final: prev: prev.lib.optionalAttrs (prev.stdenv.hostPlatform.system == "aarch64-linux") {
        mutter = prev.callPackage ../packages/mutter-hdr.nix {
          inherit (prev) mutter;
          inherit outputFrc;
        };
      })
    ];

    # The patched compositor checks the exact board, the internal DSI output,
    # the dither-enabled DTB, and the expected backlight before offering HDR.
    environment.etc."mutter/xn242-native-hdr".text = "OPD2413 XN242 native-gamma HDR candidate\n";
    environment.etc."mutter/xn242-adaptive-hdr".text = "XN242 content-adaptive global backlight with SDR white compensation\n";
    environment.etc."mutter/xn242-output-frc" = lib.mkIf outputFrc {
      text = "OPD2413 XN242 experimental 8+4-bit output dithering\n";
    };
    environment.systemPackages = [ (pkgs.callPackage ../packages/display-control.nix { }) ];
    xdg.mime = {
      enable = true;
      defaultApplications = lib.genAttrs
        [ "video/mp4" "video/x-matroska" "video/webm" "video/quicktime" ]
        (_: [ "mpv.desktop" ]);
    };
  };
}
