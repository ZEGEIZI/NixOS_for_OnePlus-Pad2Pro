# Optional fixed read-only reports for USB bring-up without unlocking accounts.
{ config, lib, pkgs, ... }:
let
  cfg = config.hardware.oneplus-pad2pro.usbNetwork;
  status = pkgs.writeShellScript "pad2pro-usb-status" (builtins.readFile ../tools/probe-status.sh);
  log = pkgs.writeShellScript "pad2pro-usb-dmesg" ''
    printf 'Content-Type: text/plain\r\n\r\n'
    exec ${pkgs.util-linux}/bin/dmesg
  '';
  previousBoot = pkgs.writeShellScript "pad2pro-usb-previous-boot" ''
    printf 'Content-Type: text/plain\r\n\r\n'
    exec ${pkgs.systemd}/bin/journalctl --boot=-1 --no-pager
  '';
in {
  options.hardware.oneplus-pad2pro.usbNetwork.diagnostics.enable =
    lib.mkEnableOption "fixed read-only hardware reports on the USB address, TCP 8080";
  config = lib.mkIf cfg.diagnostics.enable {
    assertions = [{
      assertion = cfg.enable;
      message = "USB diagnostics require hardware.oneplus-pad2pro.usbNetwork.enable.";
    }];
    networking.firewall.interfaces.usb0.allowedTCPPorts = [ 8080 ];
    systemd.services.pad2pro-usb-diagnostics = {
      description = "Read-only Pad 2 Pro USB diagnostics";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" "systemd-networkd.service" ];
      path = with pkgs; [ coreutils util-linux systemd ];
      serviceConfig = {
        Type = "simple";
        Restart = "on-failure";
        RestartSec = 3;
        RuntimeDirectory = "pad2pro-diagnostics";
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        NoNewPrivileges = true;
        ProtectKernelTunables = true;
      };
      script = ''
        mkdir -p /run/pad2pro-diagnostics/cgi-bin
        ln -sfn ${status} /run/pad2pro-diagnostics/cgi-bin/status
        ln -sfn ${log} /run/pad2pro-diagnostics/cgi-bin/dmesg
        ln -sfn ${previousBoot} /run/pad2pro-diagnostics/cgi-bin/previous-boot
        printf 'Read-only USB diagnostics: /cgi-bin/status, /cgi-bin/dmesg, /cgi-bin/previous-boot\n' \
          > /run/pad2pro-diagnostics/index.html
        exec ${pkgs.busybox}/bin/busybox httpd -f -p 192.168.77.2:8080 -h /run/pad2pro-diagnostics
      '';
    };
  };
}
