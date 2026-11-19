{
  description = "NixOS GNOME for OnePlus Pad 2 Pro (erhai), with kShimC generations";

  inputs = {
    nixpkgs.url = "https://channels.nixos.org/nixos-unstable/nixexprs.tar.xz";
    kernel-patchset = {
      url = "path:./inputs/kernel-patchset";
      flake = false;
    };
  };

  outputs = inputs@{ self, nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      eachSystem = nixpkgs.lib.genAttrs systems;
      hardwareModule = import ./modules/oneplus-pad2pro.nix {
        inherit inputs;
        kernelPackage = self.packages.aarch64-linux.kernel-base;
      };
    in {
      nixosModules = {
        oneplus-pad2pro = hardwareModule;
        kshim = import ./modules/kshim.nix;
        ram-system = import ./modules/ram-system.nix;
        default = { imports = [ hardwareModule self.nixosModules.kshim ]; };
      };
      nixosConfigurations.pad2pro = nixpkgs.lib.nixosSystem {
        system = "aarch64-linux";
        modules = [
          self.nixosModules.default ./hosts/pad2pro ./modules/native-gamma-hdr.nix
          {
            hardware.oneplus-pad2pro.kernelPackage = self.packages.aarch64-linux.kernel-base;
            hardware.oneplus-pad2pro.stockBluetoothFirmware = true;
            hardware.oneplus-pad2pro.experimentalOutputFrc = false;
          }
        ];
      };
      nixosConfigurations.pad2pro-build = nixpkgs.lib.nixosSystem {
        system = "aarch64-linux";
        modules = [
          self.nixosModules.default ./hosts/pad2pro ./modules/native-gamma-hdr.nix
          { hardware.oneplus-pad2pro.kernelPackage = self.packages.x86_64-linux.kernel-base;
            hardware.oneplus-pad2pro.stockBluetoothFirmware = true;
            hardware.oneplus-pad2pro.experimentalOutputFrc = false; }
        ];
      };
      nixosConfigurations.pad2pro-wifi-debug = self.nixosConfigurations.pad2pro-build.extendModules {
        modules = [{ boot.kernelParams = [ "ath12k.debug_mask=0x212" ]; }];
      };
      # OEM Bluetooth validation configuration, sharing the accepted daily kernel.
      nixosConfigurations.pad2pro-brahma = nixpkgs.lib.nixosSystem {
        system = "aarch64-linux";
        modules = [
          self.nixosModules.default ./hosts/pad2pro ./modules/native-gamma-hdr.nix
          {
            hardware.oneplus-pad2pro.kernelPackage = self.packages.x86_64-linux.kernel-base;
            hardware.oneplus-pad2pro.stockBluetoothFirmware = true;
            hardware.oneplus-pad2pro.experimentalOutputFrc = false;
          }
        ];
      };
      # Color kernel with the standard compositor for display diagnostics.
      nixosConfigurations.pad2pro-color = nixpkgs.lib.nixosSystem {
        system = "aarch64-linux";
        modules = [
          self.nixosModules.default ./hosts/pad2pro
          { hardware.oneplus-pad2pro.kernelPackage = self.packages.x86_64-linux.kernel-base; }
        ];
      };
      nixosConfigurations.pad2pro-hdr = self.nixosConfigurations.pad2pro;
      nixosConfigurations.pad2pro-hdr-frc = self.nixosConfigurations.pad2pro.extendModules {
        modules = [ { hardware.oneplus-pad2pro.experimentalOutputFrc = nixpkgs.lib.mkForce true; } ];
      };
      nixosConfigurations.pad2pro-hdr10 = self.nixosConfigurations.pad2pro;
      nixosConfigurations.pad2pro-probe = nixpkgs.lib.nixosSystem {
        system = "aarch64-linux";
        modules = [
          hardwareModule ./modules/diagnostic.nix
          { hardware.oneplus-pad2pro.kernelPackage = self.packages.x86_64-linux.kernel-base;
            hardware.oneplus-pad2pro.stockBluetoothFirmware = true; }
        ];
      };
      packages = eachSystem (system:
        let
          pkgs = import nixpkgs {
            inherit system;
            config.allowUnfreePredicate = import ./packages/firmware-policy.nix { lib = nixpkgs.lib; };
          };
        in {
          kshim-install = pkgs.callPackage ./packages/kshim-install.nix { };
          firmware = pkgs.callPackage ./packages/firmware.nix { };
          bluetooth-firmware = pkgs.callPackage ./packages/bluetooth-firmware.nix { };
          audio = pkgs.callPackage ./packages/audio.nix { };
          focus-camera = pkgs.callPackage ./packages/focus-camera.nix { };
          charging-desktop = pkgs.callPackage ./packages/charging.nix { };
          hdr-player = pkgs.callPackage ./packages/hdr-player.nix { };
          iris-vaapi = pkgs.callPackage ./packages/iris-vaapi.nix { };
          hdr-test-patterns = pkgs.callPackage ./packages/hdr-test-patterns.nix { };
          hdr-mutter = pkgs.callPackage ./packages/mutter-hdr.nix { };
          hdr-frc-mutter = pkgs.callPackage ./packages/mutter-hdr.nix { outputFrc = true; };
          # Both builds use the same nixpkgs toolchain and official source.
          # NixOS appends boot.kernelPatches to kernel-base exactly once.
          kernel-base = pkgs.pkgsCross.aarch64-multiplatform.callPackage ./packages/kernel.nix {
            devicePatchset = inputs.kernel-patchset;
            kernelPatches = [ ];
            applyDevicePatches = false;
          };
          kernel = pkgs.pkgsCross.aarch64-multiplatform.callPackage ./packages/kernel.nix {
            devicePatchset = inputs.kernel-patchset;
            kernelPatches = [ ];
          };
          default = self.packages.${system}.kshim-install;
        });
      checks = eachSystem (system:
        let pkgs = import nixpkgs { inherit system; };
        in {
          arm64-execution = (import nixpkgs { system = "aarch64-linux"; }).runCommand
            "pad2pro-arm64-execution" { } ''
              test "$(uname -m)" = aarch64
              printf 'ARM64 build execution works\n' > $out
            '';
          firmware-inputs = pkgs.runCommand "opd2413-bundled-firmware-tests" {
            nativeBuildInputs = [ pkgs.python3 ];
          } ''
            python3 ${./tools}/check-firmware-inputs.py --inputs ${./inputs/firmware}
            touch $out
          '';
          kernel-objects = import ./packages/kernel-objects.nix {
            inherit (pkgs) lib;
            kernel = self.packages.${system}.kernel;
          };
          charging-objects = import ./packages/kernel-objects.nix {
            inherit (pkgs) lib;
            kernel = self.packages.${system}.kernel;
            selectedObjects = [
              "drivers/iio/adc/qcom-spmi-adc5-gen3.o"
              "drivers/iio/adc/qcom-vadc-common.o"
              "drivers/thermal/qcom/qcom-spmi-adc-tm5-gen3.o"
              "drivers/soc/qcom/pmic_glink.o"
              "drivers/power/supply/qcom_battmgr.o"
              "drivers/power/supply/sc8547a.o"
              "drivers/power/supply/erhai_pps.o"
            ] ++ map (name: "drivers/power/supply/ufcs/${name}.o") [
              "ufcs_core" "sc8547a_ufcs" "ufcs_event" "ufcs_event_ctrl"
              "ufcs_event_data" "ufcs_event_vendor" "ufcs_intf" "ufcs_notify"
              "ufcs_policy_engine" "ufcs_pe_cable" "ufcs_pe_vendor" "ufcs_pe_test"
              "ufcs_sha256" "ufcs_timer"
            ];
          };
          wifi-objects = import ./packages/kernel-objects.nix {
            inherit (pkgs) lib;
            kernel = self.packages.${system}.kernel;
            selectedObjects = map (file: "drivers/net/wireless/ath/ath12k/${file}.o") [
              "core" "mac" "qmi" "reg" "wmi"
              "wifi7/dp_rx" "wifi7/hal" "wifi7/hw" "wifi7/pci"
            ];
          };
          patchset-replay = pkgs.runCommand "erhai-patchset-replay" {
            nativeBuildInputs = [ pkgs.python3 pkgs.patch pkgs.xz ];
          } ''
            python3 ${inputs.kernel-patchset}/tools/verify.py \
              --tarball ${self.packages.${system}.kernel.src} \
              --destination replay --report $out
          '';
          device-regression = pkgs.runCommand "erhai-device-regression" {
            nativeBuildInputs = [ pkgs.python3 pkgs.stdenv.cc pkgs.dtc ];
          } ''
            source=${self.packages.${system}.kernel.erhaiSource}
            cc -std=c11 -Wall -Wextra -Werror \
              "$source/tools/testing/selftests/bluetooth/brahma-peripheral-test.c" -o brahma-test
            ./brahma-test
            python3 "$source/tools/testing/selftests/tty/qcom-geni-lifecycle-test.py"
            python3 "$source/tools/testing/selftests/drm/dpu-output-dither-test.py"
            python3 "$source/tools/testing/selftests/net/ath12k-reg-event-test.py"
            python3 "$source/tools/testing/selftests/net/ath12k-range-scan-test.py"
            python3 "$source/tools/testing/selftests/net/ath12k-of-freq-test.py" \
              --dtb ${self.packages.${system}.kernel}/dtbs/qcom/sm8750-erhai.dtb
            python3 ${inputs.kernel-patchset}/tools/check-charging.py "$source"
            python3 ${inputs.kernel-patchset}/tools/check-dtb.py \
              ${self.packages.${system}.kernel}/dtbs/qcom/sm8750-erhai.dtb
            touch $out
          '';
          hdr-backlight-policy = pkgs.runCommand "xn242-hdr-backlight-policy-tests" {
            nativeBuildInputs = [ pkgs.stdenv.cc ];
          } ''
            cc -std=c11 -Wall -Wextra -Werror -include stdlib.h \
              -include ${./packages/xn242-hdr-policy.h} ${./tests/xn242_hdr_policy.c} \
              -lm -o policy-test
            ./policy-test
            touch $out
          '';
          wifi-firmware = pkgs.runCommand "opd2413-wifi-firmware-tests" {
            nativeBuildInputs = [ pkgs.python3 pkgs.stdenv.cc ];
          } ''
            python3 ${inputs.kernel-patchset}/tools/check-wifi-firmware.py \
              ${self.packages.${system}.kernel.erhaiSource}/drivers/net/wireless/ath/ath12k/core.h \
              ${inputs.kernel-patchset}/tests/wifi_firmware_path.c
            touch $out
          '';
          cps8601-firmware = pkgs.runCommand "cps8601-firmware-tests" {
            nativeBuildInputs = [ pkgs.python3 pkgs.stdenv.cc ];
          } ''
            python3 ${inputs.kernel-patchset}/tools/check-cps8601-firmware.py \
              ${self.packages.${system}.kernel.erhaiSource}/drivers/power/supply/cps8601.c \
              ${inputs.kernel-patchset}/tests/cps8601_firmware.c
            touch $out
          '';
          boot-publication = pkgs.runCommand "kshim-publication-tests" {
            nativeBuildInputs = [ (pkgs.python3.withPackages (ps: [ ps.cryptography ])) pkgs.dtc ];
          } ''
            cp -r ${./tools} tools
            cp -r ${./tests} tests
            cp -r ${./modules} modules
            mkdir -p packages
            cp -r ${./packages/charging} packages/charging
            mkdir inputs
            cp -r ${./inputs/kshim-protocol} inputs/kshim-protocol
            chmod -R u+w tools tests
            python3 tools/vendor-kshim.py --check
            python3 -m unittest discover -s tests -v
            touch $out
          '';
        });
    };
}
