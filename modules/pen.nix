{ config, lib, pkgs, ... }:
let
  cfg = config.hardware.oneplus-pad2pro.pen;
  python = pkgs.python3.withPackages (ps: [ ps.pygobject3 ps.pyudev ]);
in {
  options.hardware.oneplus-pad2pro.pen.autoConnect =
    lib.mkEnableOption "Bluetooth pairing and connection for a docked OnePlus Pencil";

  config = lib.mkIf cfg.autoConnect {
    systemd.services.erhai-pen-connect = {
      description = "Connect the docked OnePlus Pencil over Bluetooth";
      wantedBy = [ "multi-user.target" ];
      wants = [ "bluetooth.service" ];
      after = [ "bluetooth.service" ];
      environment.GI_TYPELIB_PATH = "${pkgs.glib.out}/lib/girepository-1.0";
      serviceConfig = {
        ExecStart = "${python}/bin/python3 -B ${../packages/pen/erhai-pen-connect.py}";
        Restart = "on-failure";
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ProtectKernelTunables = true;
        PrivateTmp = true;
      };
    };
  };
}
