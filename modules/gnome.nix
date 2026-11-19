{ lib, pkgs, ... }:
{
  imports = [ ./desktop-support.nix ./sensors.nix ./torch.nix ];

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

  # GNOME Console can start without WAYLAND_DISPLAY in its environment.
  # Explicit selection connects to the Wayland socket instead of probing
  # direct DRM/KMS, which is already owned by the desktop compositor.
  environment.etc."mpv/mpv.conf".text = ''
    vo=gpu-next
    gpu-api=opengl
    gpu-context=wayland
    hwdec=v4l2m2m-copy
  '';

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
          "org/gnome/shell".enabled-extensions = [
            "charge-indicator@tablet-linux"
            "erhai-torch@erhai.local"
          ];
          "org/gnome/settings-daemon/plugins/color".night-light-enabled = false;
          "org/gnome/desktop/interface".scaling-factor = lib.gvariant.mkUint32 2;
          "org/gnome/desktop/input-sources".sources = [
            (lib.gvariant.mkTuple [ "xkb" "us" ])
            (lib.gvariant.mkTuple [ "ibus" "libpinyin" ])
          ];
          # The charging inhibitor permits screen blanking while preventing
          # suspend on a wired charger; unplugging restores these idle defaults.
          "org/gnome/settings-daemon/plugins/power" = {
            sleep-inactive-ac-type = "suspend";
            sleep-inactive-ac-timeout = lib.gvariant.mkInt32 900;
            sleep-inactive-battery-type = "suspend";
            sleep-inactive-battery-timeout = lib.gvariant.mkInt32 900;
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
            ambient-enabled = false;
            sleep-inactive-ac-type = "suspend";
            sleep-inactive-ac-timeout = lib.gvariant.mkInt32 900;
            sleep-inactive-battery-type = "suspend";
            sleep-inactive-battery-timeout = lib.gvariant.mkInt32 900;
          };
        };
      }];
    };
  };

  # The Xwayland accessibility startup script invokes xprop by name.
  environment.systemPackages = with pkgs; [
    mesa-demos vulkan-tools xprop
    (callPackage ../packages/hdr-player.nix { })
  ];
}
