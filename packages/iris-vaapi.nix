{ lib, stdenv, fetchurl, meson, ninja, pkg-config, python3, gitMinimal, ffmpeg-headless, libva, libdrm, libglvnd, libgbm }:
stdenv.mkDerivation {
  pname = "iris-vaapi";
  version = "0.4.0-unstable-4125b11";

  src = fetchurl {
    name = "qualcomm-iris-vaapi-4125b1190c66.tar.gz";
    url = "https://codeload.github.com/phxinyang/qualcomm-iris-vaapi/tar.gz/4125b1190c66ff7cf46e54c2b6d4076a01d7d1cd";
    hash = "sha256-cbEn5y8XowVnSd4T+mgVip8dUG+YbVcfIUMSte5BsQQ=";
  };

  patches = [ ./iris-vaapi/disable-av1.patch ];

  nativeBuildInputs = [ meson ninja pkg-config python3 ];
  nativeCheckInputs = [ ffmpeg-headless gitMinimal ];
  buildInputs = [ libva libdrm libglvnd libgbm ];
  mesonBuildType = "release";
  doCheck = stdenv.buildPlatform.canExecute stdenv.hostPlatform;
  preCheck = ''
    export IRIS_TEST_SCRATCH_ROOT="$TMPDIR/iris-tests"
    export IRIS_AV1_INSTALL_DIR="$TMPDIR/iris-av1-install"
    export IRIS_AV1_DPB_ORACLE_DIR="$TMPDIR/iris-av1-dpb"
  '';

  # Archives have no Git metadata. Keep the driver's version deterministic.
  postPatch = ''
    patchShebangs test scripts
    substituteInPlace meson.build --replace-fail \
      "version: run_command(['sh', '-c', 'git rev-parse --short HEAD 2>/dev/null || echo unknown']," \
      "version: run_command(['sh', '-c', 'echo 4125b1190c66'],"
  '';

  postConfigure = ''
    grep -q 'iris/gpu_copy.cc' compile_commands.json
  '';

  # Install only the driver, not upstream's scripts that edit distro clients.
  installPhase = ''
    runHook preInstall
    install -Dm755 src/v4l2_drv_video.so "$out/lib/dri/v4l2_drv_video.so"
    ln -s v4l2_drv_video.so "$out/lib/dri/msm_drv_video.so"
    install -Dm644 ../COPYING "$out/share/doc/iris-vaapi/COPYING"
    for name in COPYING.MIT COPYING.LGPL AUTHORS CREDITS README.md; do
      install -m644 "../$name" "$out/share/doc/iris-vaapi/$name"
    done
    install -m644 ${./iris-vaapi/source.json} "$out/share/doc/iris-vaapi/source.json"
    runHook postInstall
  '';

  meta = {
    description = "VA-API driver for the Qualcomm Iris stateful V4L2 codec";
    homepage = "https://github.com/phxinyang/qualcomm-iris-vaapi";
    license = with lib.licenses; [ mit lgpl21Only ];
    platforms = lib.platforms.linux;
  };
}
