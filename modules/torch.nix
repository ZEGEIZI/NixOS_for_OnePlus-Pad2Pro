{ pkgs, ... }:
let
  uuid = "erhai-torch@erhai.local";
  torch = pkgs.runCommand "erhai-gnome-torch" { } ''
    install -Dm644 ${../packages/torch/extension.js} "$out/share/gnome-shell/extensions/${uuid}/extension.js"
    install -Dm644 ${../packages/torch/metadata.json} "$out/share/gnome-shell/extensions/${uuid}/metadata.json"
  '';
in {
  environment.systemPackages = [ torch ];
}
