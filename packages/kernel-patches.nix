{ lib, source }:
let
  manifest = builtins.fromJSON (builtins.readFile "${source}/patchsets/7.3/manifest.json");
  # Last fragment wins, including explicit disable requests. Mark overrides as
  # required so Kconfig dependency changes fail configuration generation.
  readConfig = file: lib.foldl' (acc: line:
    let
      setting = builtins.match "CONFIG_([A-Za-z0-9_]+)=(.*)" line;
      disabled = builtins.match "# CONFIG_([A-Za-z0-9_]+) is not set" line;
      value = if setting == null then null else builtins.elemAt setting 1;
    in if setting != null then acc // {
      ${builtins.head setting} = lib.mkForce (
        if builtins.elem value [ "y" "m" "n" ] then { tristate = value; optional = value == "n"; }
        else { freeform = if lib.hasPrefix "\"" value then builtins.fromJSON value else value; });
    } else if disabled != null then acc // {
      # Hidden/removed disabled symbols can be absent. The final .config checker
      # still rejects an enabled value, including those hidden from oldconfig.
      ${builtins.head disabled} = lib.mkForce (lib.kernel.no // { optional = true; });
    } else acc
  ) { } (lib.splitString "\n" (builtins.readFile file));
  hardwareConfig = lib.foldl' (acc: entry:
    assert lib.assertMsg
      (builtins.hashFile "sha256" "${source}/${entry.file}" == entry.sha256)
      "Erhai hardware configuration differs from its generated manifest; export the source commits again.";
    acc // readConfig "${source}/${entry.file}"
  ) { } manifest.configs;
  distributionConfig = readConfig ./nixos.config;
in
assert lib.assertMsg
  (lib.filter (line: line != "") (lib.splitString "\n"
    (builtins.readFile "${source}/patchsets/7.3/series")) == map (entry: entry.file) manifest.patches)
  "Erhai patch order differs from its generated manifest; export the source commits again.";
{
  inherit manifest;
  patches = map (entry:
    assert lib.assertMsg
      (builtins.hashFile "sha256" "${source}/patchsets/7.3/${entry.file}" == entry.sha256)
      "Erhai patch differs from its generated manifest; export the source commits again.";
    {
    name = "erhai-${entry.commit}";
    patch = builtins.path {
      path = "${source}/patchsets/7.3/${entry.file}";
      name = builtins.baseNameOf entry.file;
    };
  }) manifest.patches ++ [{
    name = "erhai-hardware-and-nixos-config";
    patch = null;
    structuredExtraConfig = hardwareConfig // distributionConfig // {
      LOCALVERSION = lib.mkForce (lib.kernel.freeform "-erhai-${manifest.release}");
      LOCALVERSION_AUTO = lib.mkForce lib.kernel.no;
    };
  }];
}
