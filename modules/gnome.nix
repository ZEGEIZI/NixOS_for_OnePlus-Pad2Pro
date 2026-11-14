{ lib, pkgs, ... }:
{
  services.desktopManager.gnome.enable = true;
  services.displayManager.gdm = {
    enable = true;
  };
  services.displayManager.defaultSession = "gnome";
  hardware.graphics = {
    enable = true;
    package = pkgs.callPackage ../packages/mesa-erhai.nix { };
  };

  services.libinput.enable = true;
  services.udisks2.enable = true;
  services.upower.enable = true;
  # UPower's generic charge-limit hwdb entry requires DMI. This DT-based
  # tablet has no DMI identity, so advertise its existing standard thresholds
  # explicitly. GNOME enables the default 75/80 policy; UPower can also reuse
  # live threshold values. See docs/GNOME.md for the driver's start=0 clamp.
  services.udev.extraRules = ''
    ACTION!="remove", SUBSYSTEM=="power_supply", KERNEL=="qcom-battmgr-bat", ATTR{model_name}=="Erhai_TABLET_*", TEST=="charge_control_start_threshold", TEST=="charge_control_end_threshold", ENV{CHARGE_LIMIT}="75,80"
  '';
  security.rtkit.enable = true;
  services.pulseaudio.enable = false;
  services.pipewire = {
    enable = true;
    alsa.enable = true;
    pulse.enable = true;
  };

  i18n.defaultLocale = "zh_CN.UTF-8";
  i18n.supportedLocales = [ "zh_CN.UTF-8/UTF-8" "en_US.UTF-8/UTF-8" ];
  i18n.inputMethod = {
    enable = true;
    type = "ibus";
    ibus.engines = [ pkgs.ibus-engines.libpinyin ];
  };
  fonts.packages = with pkgs; [ noto-fonts-cjk-sans noto-fonts-cjk-serif noto-fonts-color-emoji ];

  programs.dconf = {
    enable = true;
    profiles = {
      user.databases = [{
        # Night Light blanks this panel on the validated display stack and
        # persists across logins. Keep it off pending color-pipeline validation.
        locks = [ "/org/gnome/settings-daemon/plugins/color/night-light-enabled" ];
        settings = {
          "org/gnome/settings-daemon/plugins/color".night-light-enabled = false;
          "org/gnome/desktop/interface".scaling-factor = lib.gvariant.mkUint32 2;
          "org/gnome/desktop/input-sources".sources = [
            (lib.gvariant.mkTuple [ "xkb" "us" ])
            (lib.gvariant.mkTuple [ "ibus" "libpinyin" ])
          ];
          # Suspend/resume has not been validated for this device yet.
          "org/gnome/settings-daemon/plugins/power" = {
            sleep-inactive-ac-type = "nothing";
            sleep-inactive-battery-type = "nothing";
            power-button-action = "interactive";
          };
        };
      }];
      gdm.databases = [{
        locks = [ "/org/gnome/settings-daemon/plugins/color/night-light-enabled" ];
        settings = {
          "org/gnome/settings-daemon/plugins/color".night-light-enabled = false;
          "org/gnome/desktop/interface".scaling-factor = lib.gvariant.mkUint32 2;
          "org/gnome/settings-daemon/plugins/power" = {
            sleep-inactive-ac-type = "nothing";
            sleep-inactive-battery-type = "nothing";
          };
        };
      }];
    };
  };

  # The Xwayland accessibility startup script invokes xprop by name.
  environment.systemPackages = with pkgs; [
    firefox mesa-demos vulkan-tools xprop
    (callPackage ../packages/hdr-player.nix { })
  ];
}
