{ config, lib, pkgs, ... }:
let
  helper = pkgs.callPackage ../packages/bluetooth.nix { };
in
{
  # WCN7860 firmware boots without a public address. Supply this tablet's
  # factory identity through MGMT before BlueZ enumerates controllers.
  # Keep device identity outside the Nix store and generic system images.
  boot.kernelModules = lib.mkIf config.hardware.bluetooth.enable [ "socinfo" ];
  # Some BLE mice omit GAP discoverability flags. Let desktop discovery
  # enumerate them too; pairing and trust still require the user's action.
  hardware.bluetooth.settings.General.FilterDiscoverable = lib.mkDefault false;
  # AutoEnable powers the adapter; BlueZ's policy reconnects after link loss.
  # PipeWire 1.6 defaults reconnect_profiles to NONE, so explicitly request
  # startup A2DP connections once the active seat's audio monitor is ready.
  # The SPA plugin itself gates this on Paired && Trusted && !Blocked.
  services.pipewire.wireplumber.extraConfig."52-bluetooth-autoconnect" =
    lib.mkIf (config.hardware.bluetooth.enable && config.services.pipewire.enable) {
      "monitor.bluez.rules" = [{
        matches = [{ "device.name" = "~bluez_card.*"; }];
        actions.update-props."bluez5.auto-connect" = [ "a2dp_sink" ];
      }];
    };
  systemd.services.pad2pro-bluetooth-address = lib.mkIf config.hardware.bluetooth.enable {
    description = "Configure the OnePlus Pad 2 Pro factory Bluetooth address";
    wantedBy = [ "bluetooth.service" ];
    before = [ "bluetooth.service" ];
    after = [ "local-fs.target" "systemd-modules-load.service" ];
    unitConfig = { StartLimitIntervalSec = 600; StartLimitBurst = 3; };
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${helper}/bin/opd2413-bluetooth-address";
      StateDirectory = "oneplus-pad2pro";
      StateDirectoryMode = "0700";
      TimeoutStartSec = 100;
      Restart = "on-failure";
      RestartPreventExitStatus = [ 1 ];
      RestartSec = 2;
    };
  };
}
