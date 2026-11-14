# RAM-only NixOS stage 1 probe. Does not mount any tablet filesystem.
{ config, lib, pkgs, ... }:
let
  liveStatus = pkgs.writeScript "pad2pro-live-status" (
    "#!${pkgs.busybox}/bin/sh\n" + builtins.readFile ../tools/probe-status.sh
  );
  liveLog = pkgs.writeScript "pad2pro-live-dmesg" ''
    #!${pkgs.busybox}/bin/sh
    printf 'Content-Type: text/plain\r\n\r\n'
    exec ${pkgs.util-linux}/bin/dmesg
  '';
in {
  system.stateVersion = "26.05";
  networking.hostName = "pad2pro-probe";
  boot.loader.grub.enable = false;
  fileSystems."/" = { fsType = "tmpfs"; options = [ "mode=0755" ]; };
  boot.kernelParams = [ "rd.systemd.unit=pad2pro-probe.target" ];
  boot.initrd.systemd = {
    storePaths = [ pkgs.busybox liveStatus liveLog ];
    targets.pad2pro-probe = {
      description = "RAM-only Pad 2 Pro NixOS initrd diagnostics";
      requires = [ "sysinit.target" ];
      after = [ "sysinit.target" ];
      unitConfig.DefaultDependencies = false;
    };
    services.pad2pro-probe = {
      description = "Read-only NixOS initrd evidence over USB NCM";
      wantedBy = [ "pad2pro-probe.target" ];
      requires = [ "sys-kernel-config.mount" ];
      after = [ "sys-kernel-config.mount" "systemd-udev-settle.service" ];
      wants = [ "systemd-udev-settle.service" ];
      path = with pkgs; [ coreutils gnused iproute2 util-linux ];
      serviceConfig = { Type = "simple"; TimeoutStartSec = 30; };
      script = ''
        # The upstream usb-ncm probe allows up to ten seconds for ADSP/Type-C.
        # Use the same bounded admission here; no unbounded retry loop.
        for attempt in $(seq 1 10); do
          set -- /sys/class/udc/*
          [ ! -e "$1" ] || break
          sleep 1
        done
        ${builtins.readFile ../tools/usb-network.sh}
        ip address add 192.168.77.2/24 dev usb0
        ip link set usb0 up
        mkdir -p /run/nixos-probe/cgi-bin
        cp ${liveStatus} /run/nixos-probe/cgi-bin/status
        cp ${liveLog} /run/nixos-probe/cgi-bin/dmesg
        chmod 755 /run/nixos-probe/cgi-bin/*
        {
          echo 'NIXOS_PAD2PRO_INITRD_READY_v1'
          echo 'kernel-source=${config.boot.kernelPackages.kernel.src}'
          echo 'root-filesystems-mounted=no'
          uname -r
          cat /proc/meminfo | head -n 1
          printf 'compatible='
          tr '\000' ' ' < /sys/firmware/devicetree/base/compatible
          echo
          echo 'Block devices (no filesystem mounted):'
          lsblk -o NAME,SIZE,TYPE,FSTYPE,PARTLABEL
        } > /run/nixos-probe/index.html
        dmesg > /run/nixos-probe/dmesg.txt
        cat /run/nixos-probe/index.html > /dev/console
        exec ${pkgs.busybox}/bin/busybox httpd -f -p 192.168.77.2:8080 -h /run/nixos-probe
      '';
    };
  };
  system.build.diagnosticPayload = pkgs.runCommand "nixos-pad2pro-initrd-probe" {
    nativeBuildInputs = [ pkgs.zstd pkgs.cpio pkgs.gnugrep ];
  } ''
    mkdir -p $out
    cp ${config.boot.kernelPackages.kernel}/${config.system.boot.loader.kernelFile} $out/Image
    cp ${config.hardware.deviceTree.package}/qcom/sm8750-erhai.dtb $out/board.dtb
    cp ${config.system.build.initialRamdisk}/initrd $out/initramfs.img
    zstd -dc $out/initramfs.img | cpio -it --quiet > initrd-files
    grep -Fx ${lib.escapeShellArg (lib.removePrefix "/" (toString liveStatus))} initrd-files
    grep -Fx ${lib.escapeShellArg (lib.removePrefix "/" (toString liveLog))} initrd-files
    printf '%s\n' ${lib.escapeShellArg (lib.concatStringsSep " " config.boot.kernelParams)} > $out/cmdline
  '';
}
