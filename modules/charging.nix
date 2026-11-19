{ config, lib, pkgs, ... }:
let
  desktop = pkgs.callPackage ../packages/charging.nix { };
in {
  environment.systemPackages = [ desktop ];
  security.polkit.enable = true;
  services.udev.extraRules = ''
    ACTION=="add", SUBSYSTEM=="power_supply", KERNEL=="qcom-battmgr-bat", TEST=="charge_behaviour", TAG+="systemd", ENV{SYSTEMD_WANTS}+="tablet-charge-behaviour.service"
  '';
  systemd.services.tablet-charge-behaviour = {
    description = "Restore the tablet charging mode";
    unitConfig.ConditionPathExists = "/var/lib/tablet-charge/behaviour";
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${desktop}/libexec/tablet-charge-behaviour restore";
    };
  };

  # logind handles the lid even outside an ordinary user's GNOME session.
  # The driver's wired-charge wakeup source also protects explicit suspend.
  services.logind.settings.Login = {
    HandleLidSwitch = lib.mkForce "suspend";
    HandleLidSwitchExternalPower = "lock";
  };

  systemd.user.services.tablet-charge-idle = {
    description = "Keep GNOME awake while the wired charger remains attached";
    wantedBy = [ "org.gnome.SettingsDaemon.Power.target" ];
    partOf = [ "org.gnome.SettingsDaemon.Power.target" ];
    after = [ "gnome-session-initialized.target" ];
    serviceConfig = {
      ExecStart = "${desktop}/libexec/tablet-charge-idle";
      Restart = "on-failure";
      Slice = "session.slice";
    };
  };

}
