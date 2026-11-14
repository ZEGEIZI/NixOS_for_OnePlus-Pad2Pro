{ lib, stdenv, scx }:
let
  # Vendored libbpf headers omit __u128, required by current ARM64 UAPI
  # headers. Supply the compiler's equivalent type for native C builds.
  rustscheds = scx.rustscheds.overrideAttrs (old: {
    env = old.env // lib.optionalAttrs stdenv.hostPlatform.isAarch64 {
      CFLAGS = (old.env.CFLAGS or "") + " -D__u128=__uint128_t";
    };
  });
in
scx.full.override { scx = scx // { inherit rustscheds; }; }
