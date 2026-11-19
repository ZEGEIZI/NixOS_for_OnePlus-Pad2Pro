{ pkgs }:
let
  source = builtins.fromJSON (builtins.readFile ./sensors/sources.json);
  pins = builtins.listToAttrs (map (item: { inherit (item) name; value = item; }) source);
  pinned = name: old:
    let
      item = pins.${name};
    in {
      src = pkgs.fetchurl {
        name = item.archive;
        url =
          if name == "hexagonrpc" then
            "https://codeload.github.com/linux-msm/hexagonrpc/tar.gz/${item.upstream_commit}"
          else if name == "libssc" then
            "https://deb.debian.org/debian/pool/main/libs/libssc/${item.archive}"
          else item.url;
        sha256 = item.sha256;
      };
      patches = (old.patches or [ ]) ++ map (p:
        let path = ./sensors + "/${p.file}";
        in assert builtins.hashFile "sha256" path == p.sha256; path
      ) item.patches;
      patchFlags = [ "-p1" "--fuzz=0" ];
    };
  hexagonrpc = pkgs.hexagonrpc.overrideAttrs (pinned "hexagonrpc");
  libssc = pkgs.libssc.overrideAttrs (pinned "libssc");
  proxy = (pkgs.iio-sensor-proxy.override { inherit libssc; })
    .overrideAttrs (pinned "iio-sensor-proxy");
  scripts = pkgs.runCommand "erhai-sensor-tools" { } ''
    install -Dm755 ${./sensors/libexec/ssc-sample-gate} "$out/libexec/ssc-sample-gate"
    install -Dm755 ${./sensors/libexec/sleep-streams} "$out/libexec/sleep-streams"
    install -Dm755 ${./sensors/sbin/erhai-sensors-import-registry} "$out/bin/erhai-sensors-import-registry"
    substituteInPlace "$out/bin/erhai-sensors-import-registry" \
      --replace-fail '#!/usr/bin/python3' '#!${pkgs.python3}/bin/python3'
    substituteInPlace "$out/libexec/ssc-sample-gate" "$out/libexec/sleep-streams" \
      --replace-fail '#!/bin/sh' '#!${pkgs.runtimeShell}'
  '';
  rom = builtins.fromJSON (builtins.readFile ./sensors/rom-config.json);
  rpcRoot = pkgs.runCommand "erhai-sensor-config" { } (
    pkgs.lib.concatMapStringsSep "\n" (item:
      let src = ./sensors + "/${item.file}";
      in assert builtins.hashFile "sha256" src == item.sha256; ''
        install -Dm644 ${src} "$out/${item.install}"
      ''
    ) rom.files + ''
      ln -s /var/lib/erhai/sensors/persist/registry "$out/sensors/registry"
      ln -s /var/lib/erhai/sensors/persist/sns_reg_version "$out/sensors/sns_reg_version"
      ln -s /var/lib/erhai/sensors/socinfo "$out/socinfo"
    '');
in { inherit hexagonrpc libssc proxy scripts rpcRoot; }
