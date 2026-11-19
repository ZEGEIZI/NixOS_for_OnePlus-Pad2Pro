{ config, lib, pkgs, ... }:
let
  cfg = config.system.profileRetention;
  retain = pkgs.writeShellScriptBin "nixos-retain-system-generations" ''
    exec ${pkgs.python3}/bin/python3 -B ${./retain-system-generations.py} \
      --nix-env ${config.nix.package}/bin/nix-env \
      --keep ${toString cfg.generations} "$@"
  '';
in {
  options.system.profileRetention = {
    enable = lib.mkEnableOption "count-based retention of the NixOS system profile";
    generations = lib.mkOption {
      type = lib.types.ints.positive;
      default = 3;
      description = "Maximum system profile generations, including the selected generation.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ retain ];
    systemd.services.nixos-system-profile-retention = {
      description = "Retain ${toString cfg.generations} NixOS system profile generations";
      wantedBy = [ "multi-user.target" ];
      after = [ "local-fs.target" ];
      unitConfig.RequiresMountsFor = [ "/nix" ] ++ lib.optional config.boot.loader.kshim.enable "/boot";
      serviceConfig = {
        Type = "oneshot";
        Nice = 19;
        IOSchedulingClass = "idle";
      };
      script = ''
        ${retain}/bin/nixos-retain-system-generations
        ${lib.optionalString (config.boot.loader.kshim.enable && config.boot.loader.kshim.cleanup.enable) ''
          /run/current-system/sw/bin/nixos-kshim-cleanup
        ''}
        ${config.nix.package}/bin/nix-store --gc
      '';
    };
    systemd.paths.nixos-system-profile-retention = {
      description = "Watch system profile generations for count-based retention";
      wantedBy = [ "multi-user.target" ];
      pathConfig.PathChanged = "/nix/var/nix/profiles";
    };
  };
}
