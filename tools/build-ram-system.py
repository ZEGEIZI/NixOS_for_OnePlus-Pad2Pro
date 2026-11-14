#!/usr/bin/env python3
"""Build RAM-only NixOS with USB passwordless login or a supplied public SSH key."""
import argparse
from pathlib import Path
import subprocess
from urllib.parse import quote


def nix_string(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('${', '\\${').replace('\n', '\\n') + '"'


parser = argparse.ArgumentParser(description=__doc__)
access = parser.add_mutually_exclusive_group(required=True)
access.add_argument("--authorized-key", type=Path)
access.add_argument("--passwordless", action="store_true", help="USB-only passwordless root SSH and console autologin")
parser.add_argument("--out-link", type=Path, default=Path("result-ram-system"))
args, nix_args = parser.parse_known_args()
if args.passwordless:
    access_module = "oneplusPad2Pro.ramSystem.passwordlessLogin = true;"
else:
    key = args.authorized_key.resolve(strict=True)
    if "PRIVATE KEY" in key.read_text():
        parser.error("Supply the public .pub file, never a private key")
    subprocess.run(["ssh-keygen", "-l", "-f", str(key)], stdout=subprocess.DEVNULL, check=True)
    access_module = "oneplusPad2Pro.ramSystem.authorizedKeys = [ (builtins.readFile %s) ];" % nix_string(str(key))
repo = Path(__file__).resolve().parents[1]
uri = "git+file://" + quote(str(repo), safe="/")
expression = '''let
  project = builtins.getFlake %s;
  ram = project.nixosConfigurations.pad2pro-build.extendModules {
    modules = [ project.nixosModules.ram-system {
      %s
    } ];
  };
in ram.config.system.build.ramSystemPayload
''' % (nix_string(uri), access_module)
subprocess.run([
    "nix", "--extra-experimental-features", "nix-command flakes", "build",
    "--impure", "--expr", expression, "--out-link", str(args.out_link), "-L", *nix_args,
], cwd=repo, check=True)
