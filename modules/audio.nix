{ config, lib, pkgs, ... }:
let
  cfg = config.hardware.oneplus-pad2pro.audio;
  audio = pkgs.callPackage ../packages/audio.nix { };
  ucm = "${audio}/share/alsa/ucm2";
  rotation = ../packages/audio/speaker-rotation;
  python = pkgs.python3.withPackages (ps: [ ps.pygobject3 ]);
in {
  options.hardware.oneplus-pad2pro.audio.enable =
    lib.mkEnableOption "Pad 2 Pro AudioReach topology and UCM for speakers, microphones and DisplayPort audio";

  config = lib.mkIf cfg.enable {
    hardware.firmware = [ audio ];
    boot.initrd.extraFirmwarePaths = [ "qcom/sm8750/OnePlus-Pad-2-Pro-tplg.bin" ];
    environment.systemPackages = [ pkgs.alsa-utils ];
    environment.etc."alsa/ucm2".source = ucm;
    environment.sessionVariables.ALSA_CONFIG_UCM2 = ucm;
    # Apply also to already logged-in sessions after a service restart.
    systemd.user.services = lib.genAttrs [ "pipewire" "pipewire-pulse" "wireplumber" ]
      (_: { environment.ALSA_CONFIG_UCM2 = ucm; }) // lib.optionalAttrs config.services.pipewire.enable {
      erhai-speaker-rotation = {
        description = "Rotate speaker channels with the built-in display";
        wantedBy = [ "graphical-session.target" ];
        partOf = [ "graphical-session.target" ];
        after = [ "gnome-session-initialized.target" "pipewire.service" "wireplumber.service" ];
        path = [ config.services.pipewire.package ];
        environment.GI_TYPELIB_PATH = "${pkgs.glib.out}/lib/girepository-1.0";
        serviceConfig = {
          ExecStart = "${python}/bin/python3 -B ${rotation}/erhai-speaker-rotation ${rotation}/config.json";
          Restart = "on-failure";
          RestartSec = 2;
        };
      };
    };
    services.pipewire.configPackages = lib.mkIf config.services.pipewire.enable [ audio ];
    services.pipewire.wireplumber.extraConfig."51-erhai-speaker" = {
      "monitor.alsa.rules" = [{
        matches = [{
          "node.name" = "~alsa_output.*HiFi__Speaker__sink";
          "alsa.card_name" = "OnePlus-Pad-2-Pro";
        }];
        actions.update-props."channelmix.max-volume" = 1.0;
      }];
    };
  };
}
