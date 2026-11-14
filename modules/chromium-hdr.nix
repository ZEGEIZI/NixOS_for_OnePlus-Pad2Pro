{ lib, pkgs, ... }:
{
  nixpkgs.overlays = [
    (_final: prev: {
      chromium = prev.chromium.override {
        # PQ client preference in Mutter keeps SDR white correctly scaled;
        # retain native Wayland color management and the HDR Canvas APIs.
        # These APIs have generated base::Feature switches. Use FeatureList
        # instead of the developer-only Blink override that triggers an infobar.
        commandLineArgs = lib.concatStringsSep " " [
          "--ozone-platform=wayland"
          ("--enable-features=" + lib.concatStringsSep "," [
            "CanvasHDR"
            "CanvasToneMapping"
            "CanvasGlobalHDRHeadroom"
            "CSSVideoDynamicRangeMediaQueries"
          ])
        ];
      };
    })
  ];

  environment.systemPackages = [ pkgs.chromium ];
  xdg.mime.defaultApplications = lib.genAttrs
    [ "text/html" "x-scheme-handler/http" "x-scheme-handler/https" ]
    (_: [ "chromium-browser.desktop" ]);
}
