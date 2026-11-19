{ inputs, kernelPackage }:
{ config, lib, pkgs, ... }:
let
  cfg = config.hardware.oneplus-pad2pro;
  finalKernel = config.boot.kernelPackages.kernel;
  support = import ../packages/kernel-patches.nix {
    inherit lib;
    source = inputs.kernel-patchset;
  };
  firmware = pkgs.callPackage ../packages/firmware.nix { };
  baseFirmware = (builtins.fromJSON
    (builtins.readFile ../inputs/firmware/base.json)).files;
  wifiFirmware = (builtins.fromJSON
    (builtins.readFile ../inputs/firmware/wifi.json)).files;
  identityOverlay = pkgs.deviceTree.compileDTS {
    name = "kshim-opd2413-identity.dtbo";
    dtsFile = pkgs.writeText "kshim-opd2413-identity.dts" ''
      /dts-v1/;
      /plugin/;
      / {
        fragment@0 {
          target-path = "/";
          __overlay__ {
            compatible = "oneplus,opd2413", "oneplus,erhai", "qcom,sm8750";
          };
        };
      };
    '';
  };
  deviceTree = pkgs.runCommand "erhai-kshim-device-tree" {
    nativeBuildInputs = [ pkgs.dtc ];
  } ''
    mkdir -p $out/qcom
    fdtoverlay -i ${finalKernel}/dtbs/qcom/sm8750-erhai.dtb \
      -o $out/qcom/sm8750-erhai.dtb ${identityOverlay}
  '';
in {
  imports = [ ./usb-diagnostics.nix ./bluetooth.nix ./audio.nix ./pen.nix ];
  options.hardware.oneplus-pad2pro = {
    stockBluetoothFirmware = lib.mkEnableOption "the OPD2413 Brahma OEM Bluetooth firmware (requires the matching kernel)" // {
      default = true;
    };
    kernelPackage = lib.mkOption {
      type = lib.types.package;
      default = kernelPackage;
      description = "Official base kernel; device support is added through boot.kernelPatches.";
    };
    usbNetwork.enable = lib.mkEnableOption "USB NCM management at 192.168.77.2";
    usbNetwork.inInitrd = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Bind the USB gadget in initrd and preserve it across switch-root.";
    };
  };
  config = {
    assertions = [{
      assertion = pkgs.stdenv.hostPlatform.system == "aarch64-linux";
      message = "OnePlus Pad 2 Pro requires aarch64-linux userspace.";
    } {
      assertion = cfg.stockBluetoothFirmware == (finalKernel.opd2413StockBluetooth or false);
      message = "OPD2413 OEM Bluetooth firmware and the Brahma bootstrap kernel must be selected together.";
    }];
    nixpkgs.config.allowUnfreePredicate = import ../packages/firmware-policy.nix { inherit lib; };
    boot.kernelPackages = pkgs.linuxPackagesFor cfg.kernelPackage;
    # The external kShimC loader consumes the ARM64 Image format.
    system.boot.loader.kernelFile = "Image";
    boot.kernelPatches = support.patches;
    boot.consoleLogLevel = 6;
    boot.kernelParams = [ "console=tty0" "mem_sleep_default=s2idle" ];
    boot.initrd = {
      systemd.tpm2.enable = false;
      compressor = "zstd";
      # Fit the RAM diagnostic container and retain more generations in 1 GiB.
      compressorArgs = [ "-T4" "-19" ];
      includeDefaultModules = false;
      # SCMI CPU frequency control needs the modular CPUCP mailbox provider.
      # Filesystems and checksum libraries are built in. Avoid generic crypto
      # module aliases that are absent from the device configuration.
      availableKernelModules = lib.mkForce [ "qcom-cpucp-mbox" ];
      kernelModules = [ "qcom-cpucp-mbox" ];
      extraFirmwarePaths = (map (entry: entry.install) (baseFirmware ++ wifiFirmware))
        ++ [ "regulatory.db" "regulatory.db.p7s" ]
        ++ lib.optionals cfg.stockBluetoothFirmware
          (map (entry: entry.install) (builtins.fromJSON
            (builtins.readFile ../inputs/firmware/bluetooth.json)).files);
    };
    boot.supportedFilesystems = [ "btrfs" "ext4" ];
    security.tpm2.enable = lib.mkDefault false;
    systemd.tpm2.enable = lib.mkDefault false;
    hardware = {
      firmware = [ firmware pkgs.wireless-regdb ]
        ++ lib.optional cfg.stockBluetoothFirmware
          (pkgs.callPackage ../packages/bluetooth-firmware.nix { });
      enableRedistributableFirmware = false;
      deviceTree = {
        enable = true;
        name = "qcom/sm8750-erhai.dtb";
        # Apply the overlay with libfdt's native CLI; this also avoids depending
        # on the host Python binding used by the generic overlay wrapper.
        dtbSource = deviceTree;
      };
    };
    boot.bootspec.extensions."org.oneplus.pad2pro.v1" = {
      dtb = "${config.hardware.deviceTree.package}/qcom/sm8750-erhai.dtb";
      kernelRelease = config.boot.kernelPackages.kernel.modDirVersion;
    };
    services.logind.settings.Login = { HandlePowerKey = "ignore"; HandleLidSwitch = "ignore"; };
    console = { font = "ter-v32n"; packages = [ pkgs.terminus_font ]; };

    boot.initrd.systemd.services.pad2pro-initrd-usb = lib.mkIf
      (cfg.usbNetwork.enable && cfg.usbNetwork.inInitrd) {
      description = "Early OnePlus Pad 2 Pro USB NCM management link";
      wantedBy = [ "initrd.target" ];
      before = [ "initrd-switch-root.target" ];
      unitConfig.DefaultDependencies = false;
      requires = [ "sys-kernel-config.mount" ];
      wants = [ "systemd-udev-settle.service" "systemd-modules-load.service" ];
      after = [ "sys-kernel-config.mount" "systemd-udev-settle.service" "systemd-modules-load.service" ];
      path = with pkgs; [ coreutils gnused iproute2 ];
      serviceConfig = { Type = "oneshot"; RemainAfterExit = true; TimeoutStartSec = 30; };
      script = ''
        for attempt in $(seq 1 10); do
          set -- /sys/class/udc/*
          [ ! -e "$1" ] || break
          sleep 1
        done
        ${builtins.readFile ../tools/usb-network.sh}
        ip address replace 192.168.77.2/24 dev usb0
        ip link set usb0 up
        printf 'USB NCM bound to %s\n' "$(cat /sys/kernel/config/usb_gadget/nixos/UDC)"
      '';
    };
    systemd.services.pad2pro-usb-network = lib.mkIf
      (cfg.usbNetwork.enable && !cfg.usbNetwork.inInitrd) {
      description = "OnePlus Pad 2 Pro USB NCM management link";
      wantedBy = [ "multi-user.target" ];
      after = [ "sys-kernel-config.mount" "systemd-udev-settle.service" ];
      wants = [ "sys-kernel-config.mount" ];
      path = with pkgs; [ coreutils gnused iproute2 ];
      serviceConfig = { Type = "oneshot"; RemainAfterExit = true; };
      script = builtins.readFile ../tools/usb-network.sh;
    };
    networking.networkmanager.unmanaged = lib.mkIf cfg.usbNetwork.enable [ "interface-name:usb0" ];
    systemd.network.enable = lib.mkIf cfg.usbNetwork.enable true;
    # networkd manages only the optional USB cable; NetworkManager owns Wi-Fi.
    systemd.network.wait-online.enable = lib.mkIf cfg.usbNetwork.enable (lib.mkDefault false);
    systemd.network.networks."30-pad2pro-usb" = lib.mkIf cfg.usbNetwork.enable {
      matchConfig.Name = "usb0";
      address = [ "192.168.77.2/24" ];
      linkConfig.RequiredForOnline = "no";
      networkConfig = { DHCP = "no"; LinkLocalAddressing = "no"; };
    };
  };
}
