{ config, pkgs, ... }:
let
  declared = pkgs.writeText "declared-system-accounts.json"
    (builtins.toJSON (builtins.attrNames config.users.users));
  preserve = "${pkgs.python3}/bin/python3 -B ${../tools/preserve-account-ranges.py}";
in {
  # Applies to arbitrary chosen names, including accounts created through GNOME.
  users.mutableUsers = true;
  users.defaultUserShell = pkgs.fish;
  programs.fish.enable = true;

  # The standard users activation rewrites these tables even with mutableUsers.
  # Retain ranges belonging to accounts outside the declarative user spec.
  system.activationScripts.save-account-ranges = {
    text = "${preserve} save --declared ${declared}";
  };
  system.activationScripts.users.deps = [ "save-account-ranges" ];
  system.activationScripts.restore-account-ranges = {
    deps = [ "users" ];
    text = "${preserve} restore --declared ${declared}";
  };
}
