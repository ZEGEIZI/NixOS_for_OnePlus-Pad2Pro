#!/usr/bin/env bash
# Build and export an installation bundle on the PC. Does not access a tablet.
set -euo pipefail
if [[ $# -lt 2 || $# -gt 3 || -e $1 || ! -f $2 ]]; then
  echo "Usage: $0 NEW-OUTPUT-DIRECTORY SIGNING-KEY-FILE [LOCAL-CONFIG]" >&2
  exit 2
fi
bundle=$(realpath -m -- "$1")
signing_key=$(realpath -- "$2")
local_config=
if [[ $# == 3 ]]; then
  local_config=$(realpath -- "$3")
  if [[ ! -f $local_config ]]; then
    echo "LOCAL-CONFIG must be an existing Nix module" >&2
    exit 2
  fi
fi
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo"
mkdir -p "$bundle/config"
# Build exactly the exported source. An explicit path flake includes local.nix,
# even though Git excludes it; private keys and work artifacts stay outside it.
tar -cf - --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='hosts/pad2pro/local.nix' \
  --exclude='inputs/local' \
  flake.nix flake.lock hosts modules packages tools tests docs inputs README.md NOTICE AGENTS.md .gitignore \
  | tar -xf - -C "$bundle/config"
if [[ -n $local_config ]]; then
  cp -- "$local_config" "$bundle/config/hosts/pad2pro/local.nix"
fi
flake="path:$bundle/config"
nix build "$flake#nixosConfigurations.pad2pro-build.config.system.build.toplevel" \
  --out-link "$bundle/system" -L
nix build "$flake#nixosConfigurations.pad2pro-build.config.system.build.kshimBootImage" \
  --out-link "$bundle/boot-image" -L
cp -L "$bundle/boot-image" "$bundle/linux-boot.ext4"
rm "$bundle/boot-image"
nix store sign --recursive --key-file "$signing_key" "$(readlink -f "$bundle/system")"
nix copy --to "file://$bundle/cache" "$(readlink -f "$bundle/system")"
nix key convert-secret-to-public < "$signing_key" > "$bundle/cache-key.pub"
printf '%s\n' "$(readlink -f "$bundle/system")" > "$bundle/system-path"
(cd "$bundle" && sha256sum linux-boot.ext4 > linux-boot.ext4.sha256)
echo "Exported $bundle; no device accessed."
