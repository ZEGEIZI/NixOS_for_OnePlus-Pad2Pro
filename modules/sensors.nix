{ config, lib, pkgs, ... }:
let
  cfg = config.hardware.oneplus-pad2pro.sensors;
  inherit (import ../packages/sensors.nix { inherit pkgs; }) hexagonrpc libssc proxy scripts rpcRoot;
  registry = "/var/lib/erhai/sensors/persist/registry";
  device = "dev-erhai\\x2dsensors\\x2dfastrpc.device";
in {
  options.hardware.oneplus-pad2pro.sensors.enable =
    lib.mkEnableOption "Qualcomm SSC sensors for rotation and ambient brightness";

  config = lib.mkIf cfg.enable {
    nixpkgs.overlays = [ (_final: prev: {
      gnome-settings-daemon = prev.gnome-settings-daemon.overrideAttrs (old: {
        patches = (old.patches or [ ]) ++ [ ../packages/sensors/ambient-absolute-curve.patch ];
      });
    }) ];

    environment.etc."gnome-settings-daemon/ambient-brightness-curve".source =
      ../packages/sensors/ambient-brightness-curve;

    hardware.sensor.iio = { enable = true; package = proxy; };
    environment.systemPackages = [ scripts libssc ];
    users.groups.fastrpc = { };
    users.users.fastrpc = { isSystemUser = true; group = "fastrpc"; };
    systemd.tmpfiles.rules = [ "d /var/lib/erhai/sensors 0750 root fastrpc -" ];
    services.udev.extraRules = ''
      ACTION!="remove", SUBSYSTEM=="misc", KERNEL=="fastrpc-adsp|fastrpc-adsp-secure", GROUP="fastrpc", MODE="0660", SYMLINK+="erhai-sensors-fastrpc", TAG+="systemd", ENV{IIO_SENSOR_PROXY_TYPE}="ssc-accel ssc-light ssc-compass ssc-gyro", ENV{ACCEL_MOUNT_MATRIX}="0, 1, 0; -1, 0, 0; 0, 0, 1", ENV{SYSTEMD_WANTS}+="iio-sensor-proxy.service"
    '';

    systemd.services.erhai-sensors-rpcd = {
      description = "FastRPC file server for the Erhai sensor domain";
      bindsTo = [ device ];
      after = [ device "systemd-tmpfiles-setup.service" ];
      unitConfig.ConditionDirectoryNotEmpty = registry;
      serviceConfig = {
        ExecStart = "${hexagonrpc}/bin/hexagonrpcd -f /dev/erhai-sensors-fastrpc -d adsp -s -R ${rpcRoot}";
        User = "fastrpc";
        Group = "fastrpc";
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        PrivateNetwork = true;
        DevicePolicy = "closed";
        DeviceAllow = [ "/dev/erhai-sensors-fastrpc rw" ];
        RestrictAddressFamilies = [ "AF_UNIX" ];
      };
    };
    systemd.services.erhai-sensors-gate = {
      description = "Check Erhai accelerometer readings before exporting sensors";
      requires = [ "erhai-sensors-rpcd.service" ];
      after = [ "erhai-sensors-rpcd.service" ];
      unitConfig.ConditionDirectoryNotEmpty = registry;
      path = [ pkgs.coreutils pkgs.gawk pkgs.gnused ];
      environment = { LC_ALL = "C"; ERHAI_SENSORS_SSCCLI = "${libssc}/bin/ssccli"; };
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = "${scripts}/libexec/ssc-sample-gate";
        User = "fastrpc";
        Group = "fastrpc";
        RuntimeDirectory = "erhai-sensors";
        TimeoutStartSec = 30;
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateDevices = true;
        RestrictAddressFamilies = [ "AF_UNIX" "AF_QIPCRTR" ];
      };
    };
    systemd.services.iio-sensor-proxy = {
      requires = [ "erhai-sensors-gate.service" ];
      after = [ "erhai-sensors-gate.service" ];
      unitConfig.ConditionDirectoryNotEmpty = registry;
    };
    systemd.services.erhai-sensors-sleep = {
      description = "Pause Erhai sensor streams during system sleep";
      before = [ "sleep.target" ];
      wantedBy = [ "sleep.target" ];
      unitConfig.StopWhenUnneeded = true;
      path = [ pkgs.coreutils config.systemd.package ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = "${scripts}/libexec/sleep-streams pause";
        ExecStop = "${scripts}/libexec/sleep-streams resume";
        RuntimeDirectory = "erhai-sensors-sleep";
        RuntimeDirectoryMode = "0700";
        TimeoutStartSec = 30;
        TimeoutStopSec = 30;
      };
    };
  };
}
