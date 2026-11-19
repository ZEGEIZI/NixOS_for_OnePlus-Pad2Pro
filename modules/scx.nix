{ pkgs, ... }:
{
  # scx.full contains schedulers and scxtop; scx-loader supplies scxtui,
  # scxctl, the D-Bus service and its polkit policy through this NixOS module.
  services.scx-loader = {
    enable = true;
    schedsPackages = [ (pkgs.callPackage ../packages/scx.nix { }) ];
    # Start the manager at boot, leaving scheduler selection to the user.
    config = {
      default_sched = null;
      # A null scheduler is omitted from TOML; the loader rejects empty files.
      default_mode = "Auto";
    };
  };
}
