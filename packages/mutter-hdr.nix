{ lib, mutter, outputFrc ? false }:
mutter.overrideAttrs (old: {
  # Try the patches on the Mutter selected by nixpkgs. Patch application and
  # compilation report incompatibilities instead of rejecting version numbers.
  # Both output paths are always available; the module selects the startup
  # default, and the session D-Bus API allows switching without logging out.
  patches = (old.patches or [ ]) ++ [
    ./patches/mutter-xn242-native-gamma-hdr.patch
    ./patches/mutter-xn242-output-frc.patch
    ./patches/mutter-xn242-adaptive-hdr.patch
    ./patches/mutter-xn242-pq-preferred.patch
  ];
  postPatch = (old.postPatch or "") + ''
    cp ${./xn242-hdr-policy.h} src/backends/meta-xn242-hdr-policy.h
  '';
})
