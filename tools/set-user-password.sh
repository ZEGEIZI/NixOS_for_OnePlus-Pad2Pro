#!/usr/bin/env bash
# Run in the user's own terminal; never pass a password as an argument or log it.
set -euo pipefail
if [[ $# != 1 || ! $1 =~ ^[a-zA-Z_][a-zA-Z0-9_.-]*$ ]]; then
  printf 'Usage: %s USERNAME\n' "$0" >&2
  exit 2
fi
account_name=$1
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
known_file=$(cat "$repo/.work/ram-access/password-setup-known-hosts-path")
[[ $known_file = /* ]] || known_file="$repo/$known_file"
test -f "$known_file"
remote_script='
    set -e
    case "$(cat /proc/cmdline)" in *pad2pro.ram=1*) ;; *) exit 1 ;; esac
    test "$(findmnt -n -o PARTLABEL --mountpoint /mnt)" = NixOS_Root
    test "$(findmnt -n -o PARTLABEL --mountpoint /mnt/nix)" = NixOS_Root
    exec nixos-enter --root /mnt -c '
printf -v password_command '%q' "passwd -- $account_name"
remote_script+="$password_command"
# POSIX quoting works with either Bash or Fish as the remote login shell.
remote_script=${remote_script//\'/\'\\\'\'}
exec ssh -t \
  -o UserKnownHostsFile="$known_file" -o StrictHostKeyChecking=yes \
  -o PreferredAuthentications=none -o PubkeyAuthentication=no \
  -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no \
  -o IdentityAgent=none root@192.168.77.2 "bash -c '$remote_script'"
