{ config, lib, pkgs, ... }:
{
  imports = [ ../../modules/gnome.nix ../../modules/user-defaults.nix ../../modules/scx.nix
    ../../modules/system-profile-retention.nix ../../modules/video-decoding.nix
    ../../modules/charging.nix ]
    ++ lib.optional (builtins.pathExists ./local.nix) ./local.nix;
  networking.hostName = "pad2pro";
  hardware.oneplus-pad2pro.audio.enable = true;
  hardware.oneplus-pad2pro.pen.autoConnect = true;
  hardware.oneplus-pad2pro.sensors.enable = true;
  time.timeZone = "Asia/Shanghai";
  system.stateVersion = "26.05";
  documentation.nixos.enable = false;
  documentation.doc.enable = false;
  documentation.info.enable = false;

  fileSystems = {
    "/" = {
      device = "/dev/disk/by-partlabel/NixOS_Root";
      fsType = "btrfs";
      options = [ "subvol=@nixos-root" "compress=zstd:1" "noatime" ];
    };
    "/nix" = {
      device = "/dev/disk/by-partlabel/NixOS_Root";
      fsType = "btrfs";
      options = [ "subvol=@nixos-nix" "compress=zstd:1" "noatime" ];
      neededForBoot = true;
    };
    "/home" = {
      device = "/dev/disk/by-partlabel/NixOS_Root";
      fsType = "btrfs";
      options = [ "subvol=@nixos-home" "compress=zstd:1" "noatime" ];
    };
    "/var/log" = {
      device = "/dev/disk/by-partlabel/NixOS_Root";
      fsType = "btrfs";
      options = [ "subvol=@nixos-log" "compress=zstd:1" "noatime" ];
    };
    "/boot" = {
      device = "/dev/disk/by-partlabel/KShinC_BOOT";
      fsType = "ext4";
      # kShimC cannot replay the ext4 journal after an unclean reset.
      # The installer/cleanup remount rw only while publishing boot files.
      options = [ "ro" "noatime" ];
    };
  };

  boot.loader.kshim.enable = true;
  boot.loader.kshim.configurationLimit = 5;
  boot.loader.kshim.cleanup.enable = true;
  # Set the actual GPT PARTUUID in local.nix before live boot publication.
  boot.loader.kshim.bootPartlabel = "KShinC_BOOT";

  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "yes";
      PasswordAuthentication = true;
      KbdInteractiveAuthentication = false;
    };
  };
  networking.networkmanager.enable = true;
  networking.firewall.enable = false;
  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    # NJU mirrors the official cache and uses its existing signing key.
    substituters = [
      "https://mirror.nju.edu.cn/nix-channels/store?priority=10"
      "https://cache.nixos.org/?priority=40"
    ];
  };
  nix.gc.automatic = false;
  system.profileRetention = { enable = true; generations = 3; };
  system.autoUpgrade.enable = false;
  zramSwap = { enable = true; algorithm = "zstd"; memoryPercent = 50; };
  services.journald.settings.Journal = { SystemMaxUse = "256M"; RuntimeMaxUse = "64M"; };
  environment.systemPackages = with pkgs; [
    gitMinimal vim nano btrfs-progs e2fsprogs usbutils pciutils iw ethtool
    htop kitty fastfetch
    nvtopPackages.msm
    papirus-icon-theme gnome-tweaks
    # Userspace tools build natively even when the kernel is cross compiled.
    ((config.boot.kernelPackages.cpupower.override { stdenv = pkgs.stdenv; }).overrideAttrs (_: {
      # The device patchset does not change tools/power/cpupower.
      patches = [ ];
    }))
  ];
}
