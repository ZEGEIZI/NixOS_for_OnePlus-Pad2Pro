# Full NixOS in RAM, for validation and explicitly authorised installation work.
{ config, lib, pkgs, modulesPath, utils, ... }:
let
  cfg = config.oneplusPad2Pro.ramSystem;
  storeMount = utils.escapeSystemdPath "/sysroot/nix/.ro-store" + ".mount";
in {
  imports = [ "${modulesPath}/installer/netboot/netboot.nix" ];
  options.oneplusPad2Pro.ramSystem = {
    authorizedKeys = lib.mkOption {
      type = lib.types.listOf lib.types.singleLineStr;
      default = [ ];
      description = "Temporary public SSH keys for the RAM system; never private keys.";
    };
    passwordlessLogin = lib.mkEnableOption "passwordless USB SSH and console root login in RAM";
  };
  config = {
    assertions = [{
      assertion = cfg.passwordlessLogin || cfg.authorizedKeys != [ ];
      message = "The RAM system requires a temporary SSH public key or explicit passwordlessLogin.";
    }];
    networking.hostName = lib.mkForce "pad2pro-ram";
    boot.loader.kshim.enable = lib.mkForce false;
    boot.loader.grub.enable = false;
    boot.kernelParams = [ "pad2pro.ram=1" "rd.systemd.gpt_auto=no" "systemd.gpt_auto=no" ];
    fileSystems = lib.mkForce {
      "/" = { fsType = "tmpfs"; options = [ "mode=0755" ]; };
      "/nix/.ro-store" = {
        fsType = "squashfs";
        device = "../nix-store.squashfs";
        options = [ "loop" ];
        neededForBoot = true;
      };
      "/nix/.rw-store" = {
        fsType = "tmpfs";
        options = [ "mode=0755" ];
        neededForBoot = true;
      };
      "/nix/store" = {
        overlay = {
          lowerdir = [ "/nix/.ro-store" ];
          upperdir = "/nix/.rw-store/store";
          workdir = "/nix/.rw-store/work";
        };
        neededForBoot = true;
      };
    };
    # The gadget survives switch-root; stage 2 only manages its IP address.
    hardware.oneplus-pad2pro.usbNetwork.enable = true;
    hardware.oneplus-pad2pro.usbNetwork.inInitrd = lib.mkForce true;
    services.openssh.settings = {
      PermitRootLogin = lib.mkForce (if cfg.passwordlessLogin then "yes" else "prohibit-password");
      PasswordAuthentication = lib.mkForce cfg.passwordlessLogin;
      PermitEmptyPasswords = cfg.passwordlessLogin;
    };
    services.openssh.listenAddresses = lib.mkIf cfg.passwordlessLogin
      (lib.mkForce [ { addr = "192.168.77.2"; } ]);
    services.openssh.openFirewall = lib.mkIf cfg.passwordlessLogin (lib.mkForce false);
    networking.firewall.interfaces.usb0.allowedTCPPorts = lib.mkIf cfg.passwordlessLogin [ 22 ];
    security.pam.services.sshd.allowNullPassword = cfg.passwordlessLogin;
    services.getty.autologinUser = lib.mkIf cfg.passwordlessLogin "root";
    users.users.root = {
      openssh.authorizedKeys.keys = cfg.authorizedKeys;
      initialHashedPassword = lib.mkIf cfg.passwordlessLogin (lib.mkForce "");
    };
    environment.systemPackages = with pkgs; [ gptfdisk nixos-install-tools ];
    netboot.squashfsCompression = "zstd -Xcompression-level 6";
    boot.postBootCommands = ''
      ${pkgs.nix}/bin/nix-store --load-db < /nix/store/nix-path-registration
    '';
    boot.initrd.systemd.services = {
      pad2pro-ram-store = {
        description = "Fetch and verify the RAM Nix store before mounting it";
        unitConfig.DefaultDependencies = false;
        requiredBy = [ storeMount ];
        before = [ storeMount ];
        requires = [ "pad2pro-initrd-usb.service" ];
        after = [ "pad2pro-initrd-usb.service" ];
        path = with pkgs; [ coreutils curl ];
        serviceConfig = { Type = "oneshot"; RemainAfterExit = true; TimeoutStartSec = 240; };
        script = builtins.readFile ../tools/fetch-ram-store.sh;
      };
    };
    system.build.ramSystemPayload = pkgs.runCommand "nixos-pad2pro-ram-system" { } ''
      mkdir -p $out
      cp ${config.boot.kernelPackages.kernel}/${config.system.boot.loader.kernelFile} $out/Image
      cp ${config.hardware.deviceTree.package}/qcom/sm8750-erhai.dtb $out/board.dtb
      cp ${config.system.build.initialRamdisk}/initrd $out/initramfs.img
      cp ${config.system.build.squashfsStore} $out/rootfs.squashfs
      digest=$(sha256sum $out/rootfs.squashfs)
      digest=''${digest%% *}
      ln -s rootfs.squashfs "$out/rootfs-$digest.squashfs"
      printf '%s init=%s/init pad2pro.ram.sha256=%s\n' \
        ${lib.escapeShellArg (lib.concatStringsSep " " config.boot.kernelParams)} \
        ${config.system.build.toplevel} "$digest" > $out/cmdline
      printf '%s\n' ${config.system.build.toplevel} > $out/system-path
    '';
  };
}
