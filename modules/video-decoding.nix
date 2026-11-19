{ ... }:
{
  imports = [ ./firefox-video.nix ];

  nixpkgs.overlays = [
    (final: prev: {
      # Use nixpkgs' complete FFmpeg feature set for the player.
      ffmpeg-iris = prev.ffmpeg.overrideAttrs (old: {
        patches = (old.patches or [ ]) ++ [ ../packages/patches/ffmpeg-v4l2-p010-source-change.patch ];
      });
      mpv-unwrapped = prev.mpv-unwrapped.override { ffmpeg = final.ffmpeg-iris; };
    })
  ];
}
