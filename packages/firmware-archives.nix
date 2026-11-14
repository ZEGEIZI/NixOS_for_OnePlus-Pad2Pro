let
  root = ../inputs/firmware;
  inventory = builtins.fromJSON (builtins.readFile (root + /archives.json));
  checked = name: entry:
    let archive = root + "/${entry.file}";
    in if builtins.hashFile "sha256" archive != entry.sha256 then
      throw "Bundled ${name} firmware archive failed SHA-256 verification; restore the matching Git version."
    else archive;
in builtins.mapAttrs checked inventory.archives
