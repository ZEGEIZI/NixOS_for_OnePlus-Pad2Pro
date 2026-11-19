{ pkgs, ... }:
{
  hardware.graphics.extraPackages = [ (pkgs.callPackage ../packages/iris-vaapi.nix { }) ];

  programs.firefox = {
    enable = true;
    preferencesStatus = "default";
    preferences = {
      "media.hardware-video-decoding.enabled" = true;
      "media.ffmpeg.vaapi.enabled" = true;
      "media.hardware-video-decoding-vulkan.enabled" = false;
    };
  };

  environment.systemPackages = [ pkgs.libva-utils ];
}
