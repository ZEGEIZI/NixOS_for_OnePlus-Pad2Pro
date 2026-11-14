{ config, lib, pkgs, ... }:
let
  cfg = config.boot.loader.kshim;
  installer = pkgs.callPackage ../packages/kshim-install.nix { };
  cleanup = pkgs.writeShellScriptBin "nixos-kshim-cleanup" ''
    exec ${installer}/bin/nixos-kshim-prune \
      --boot-dir /boot \
      --partlabel ${lib.escapeShellArg cfg.bootPartlabel} \
      ${lib.optionalString (cfg.bootPartuuid != null) "--partuuid ${lib.escapeShellArg cfg.bootPartuuid}"} \
      --configuration-limit ${toString cfg.configurationLimit} \
      ${lib.optionalString (!cfg.cleanup.keepPrevious) "--no-keep-previous"} \
      ${lib.concatMapStringsSep " " (v: "--keep-version ${lib.escapeShellArg v}") cfg.cleanup.keepVersions} \
      "$@"
  '';
in {
  options.boot.loader.kshim = {
    enable = lib.mkEnableOption "the kShimC boot entry installer for NixOS";
    configurationLimit = lib.mkOption {
      type = lib.types.ints.unsigned;
      default = 10;
      description = ''
        Maximum number of newest system profile generations represented in
        the boot menu (0 means all surviving profile generations). Protected
        running, activated, selected, previous and pinned entries may exceed
        this limit. Does not delete Nix system profiles or run store GC.
      '';
    };
    cleanup = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Synchronize boot entries on installation and system profile changes.";
      };
      keepPrevious = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Keep the previous boot entry even after its system profile is deleted.";
      };
      keepVersions = lib.mkOption {
        type = lib.types.listOf (lib.types.strMatching "[A-Za-z0-9_-][A-Za-z0-9_.-]{0,62}");
        default = [];
        example = [ "nixos-06f3e4b35a208da7db344a74adbfc516" ];
        description = "Existing boot identifiers to pin as additional recovery entries with their GC roots.";
      };
    };
    bootPartlabel = lib.mkOption { type = lib.types.str; default = "KShinC_BOOT"; };
    bootPartuuid = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Actual boot GPT PARTUUID, required before live installation.";
    };
  };
  config = lib.mkIf cfg.enable {
    boot.loader.external.enable = true;
    boot.loader.external.installHook = pkgs.writeShellScript "install-kshim-generation" ''
      set -e
      ${installer}/bin/nixos-kshim-install \
        --boot-dir /boot \
        --partlabel ${lib.escapeShellArg cfg.bootPartlabel} \
        ${lib.optionalString (cfg.bootPartuuid != null) "--partuuid ${lib.escapeShellArg cfg.bootPartuuid}"} \
        "$1"
      ${lib.optionalString cfg.cleanup.enable ''
        # A fresh nixos-install target has no booted/activated runtime yet.
        # Defer cleanup there until a later profile change or manual run.
        if test -e /run/booted-system && test -e /run/current-system; then
          ${cleanup}/bin/nixos-kshim-cleanup
        fi
      ''}
    '';
    environment.systemPackages = [ installer ] ++ lib.optional cfg.cleanup.enable cleanup;
    systemd.services.kshim-cleanup = lib.mkIf cfg.cleanup.enable {
      description = "Synchronize kShimC boot entries with NixOS system generations";
      after = [ "local-fs.target" "nix-gc.service" ];
      unitConfig.RequiresMountsFor = [ "/boot" "/nix" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${cleanup}/bin/nixos-kshim-cleanup";
        StateDirectory = "kshim";
        UMask = "0077";
      };
    };
    systemd.paths.kshim-cleanup = lib.mkIf cfg.cleanup.enable {
      description = "Watch NixOS system generation changes for kShimC cleanup";
      wantedBy = [ "multi-user.target" ];
      pathConfig.PathChanged = "/nix/var/nix/profiles";
    };
    system.build.kshimBootTree = pkgs.runCommand "nixos-kshim-boot-tree" {
      nativeBuildInputs = [ installer ];
    } ''
      nixos-kshim-install --staging-root $out ${config.system.build.toplevel}
    '';
    system.build.kshimBootImage = pkgs.runCommand "nixos-kshim-boot-ext4.img" {
      nativeBuildInputs = [ pkgs.e2fsprogs pkgs.coreutils ];
    } ''
      truncate -s 1G $out
      export E2FSPROGS_FAKE_TIME=1
      mkfs.ext4 -F -b 4096 -I 256 \
        -O none,has_journal,ext_attr,resize_inode,dir_index,filetype,extent,64bit,flex_bg,sparse_super,large_file,huge_file,dir_nlink,extra_isize,metadata_csum \
        -E lazy_itable_init=0,lazy_journal_init=0 \
        -L KShinC_BOOT -d ${config.system.build.kshimBootTree} $out
    '';
  };
}
