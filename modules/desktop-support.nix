{ pkgs, ... }:
let
  ipaConfig = "${./desktop-support/camera-ipa}";
in {
  services.udev.extraHwdb = builtins.readFile ./desktop-support/99-erhai-pogo-esc.hwdb;
  services.udev.extraRules = builtins.readFile ./desktop-support/90-erhai-internal-storage.rules;
  environment.etc."libinput/local-overrides.quirks".source =
    ./desktop-support/31-erhai-pogo-keyboard.quirks;

  # libcamera searches this directory before its built-in tuning files.
  environment.sessionVariables.LIBCAMERA_IPA_CONFIG_PATH = ipaConfig;
  systemd.user.services.wireplumber.environment.LIBCAMERA_IPA_CONFIG_PATH = ipaConfig;
  environment.systemPackages = [ (pkgs.callPackage ../packages/focus-camera.nix { }) ];
}
