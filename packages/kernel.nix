{ lib, linux_7_3, buildPackages, devicePatchset, applyDevicePatches ? true
, kernelPatches ? [ ], randstructSeed ? "", features ? { } }:
let
  support = import ./kernel-patches.nix { inherit lib; source = devicePatchset; };
  devicePatchFiles = map (p: toString p.patch) (lib.filter (p: p.patch != null) support.patches);
  inherit (support) manifest;
  dtbChecker = builtins.path {
    path = "${devicePatchset}/tools/check-dtb.py";
    name = "erhai-dtb-check.py";
  };
  release = "${linux_7_3.version}-erhai-${manifest.release}";
  versionConfig = buildPackages.writeText "erhai-release.config" ''
    CONFIG_LOCALVERSION="-erhai-${manifest.release}"
    # CONFIG_LOCALVERSION_AUTO is not set
  '';
  kernel = linux_7_3.override (args: {
    pname = "linux-erhai";
    argsOverride = (args.argsOverride or { }) // { modDirVersion = release; };
    autoModules = false;
    # Preserve the previous defconfig + hardware + NixOS fragment policy.
    # Do not request settings for unrelated platforms' disabled driver menus.
    enableCommonConfig = false;
    ignoreConfigErrors = false;
    # Seed all dependencies before nixpkgs' interactive config refinement;
    # otherwise a built-in request can be capped by a later modular dependency.
    defconfig = "defconfig sm8750-peripherals.config erhai-firstboot.config";
    inherit randstructSeed;
    features = lib.recursiveUpdate ((args.features or { }) // { efiBootStub = false; }) features;
    kernelPatches = (args.kernelPatches or [ ])
      ++ lib.optionals applyDevicePatches support.patches ++ kernelPatches;
  });
  preparedSource = buildPackages.runCommand "erhai-patched-source-${release}" {
    nativeBuildInputs = with buildPackages; [ gnutar xz patch ];
  } ''
    mkdir source
    tar -xf ${kernel.src} --strip-components=1 -C source
    chmod -R u+w source
    cd source
    ${lib.concatMapStringsSep "\n" (patch:
      "patch --batch --forward ${lib.optionalString (builtins.elem (toString patch) devicePatchFiles) "--fuzz=0"} -p1 < ${patch}"
    ) kernel.patches}
    mkdir -p $out
    cp -r . $out/
  '';
in
assert lib.assertMsg (lib.versions.majorMinor linux_7_3.version == manifest.series
  && lib.versionAtLeast linux_7_3.version manifest.minimum_version)
  "Erhai requires its supported official kernel series; port forward instead of downgrading.";
kernel.overrideAttrs (old: {
  # Check the compile tree against strict replay. generic.nix also constructs
  # its configuration from this official source and the same kernelPatches.
  postPatch = (old.postPatch or "") + ''
    ${lib.concatMapStringsSep "\n" (file:
      if support.manifest.result_files_sha256.${file} == null then
        "test ! -e ${lib.escapeShellArg file}"
      else "cmp ${lib.escapeShellArg file} ${lib.escapeShellArg "${preparedSource}/${file}"}"
    ) (builtins.attrNames support.manifest.result_files_sha256)}
  '';
  postConfigure = (old.postConfigure or "") + ''
    ${buildPackages.python3}/bin/python3 ${../tools/check-kernel-config.py} "$buildRoot/.config" \
      arch/arm64/configs/sm8750-peripherals.config \
      arch/arm64/configs/erhai-firstboot.config ${./nixos.config} ${versionConfig}
  '';
  postInstall = (old.postInstall or "") + ''
    ${buildPackages.python3}/bin/python3 ${dtbChecker} \
      --fdtget ${buildPackages.dtc}/bin/fdtget "$out/dtbs/qcom/sm8750-erhai.dtb"
  '';
  passthru = old.passthru // {
    opd2413StockBluetooth = true;
    erhaiPatchset = manifest.release;
    erhaiSource = preparedSource;
  };
})
