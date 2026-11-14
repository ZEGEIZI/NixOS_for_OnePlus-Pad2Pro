{ lib, mesa }:
(mesa.override {
  galliumDrivers = [ "freedreno" "llvmpipe" "softpipe" "zink" ];
  vulkanDrivers = [ "freedreno" "swrast" ];
}).overrideAttrs (old: {
  # Follow nixpkgs without a version gate. Keep upstream-source.json as patch
  # provenance; patch application and compilation detect incompatibilities.
  # Freedreno does not implement Mesa's VA-API video state tracker.
  mesonFlags = old.mesonFlags ++ [ (lib.mesonEnable "gallium-va" false) ];
  patches = (old.patches or [ ]) ++ [
    ./mesa/piano-fixes.patch
    ./mesa/turnip-a8xx-runtime-unroll.patch
    ./mesa/turnip-ssbo-wide-reads.patch
    ./mesa/turnip-a8xx-word-reuse.patch
    ./mesa/freedreno-thread-safe-tex-seqno.patch
    ./mesa/freedreno-explicit-sync.patch
  ];
})
