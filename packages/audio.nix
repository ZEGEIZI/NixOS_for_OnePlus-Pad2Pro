{ lib, runCommand, gnutar, gzip, m4, alsa-utils, alsa-ucm-conf }:
let
  audio = ./audio;
  manifest = builtins.fromJSON (builtins.readFile (audio + /source.json));
in runCommand "erhai-audio" {
  nativeBuildInputs = [ gnutar gzip m4 alsa-utils ];
  meta.license = lib.licenses.bsd3;
} ''
  # Compile the locally maintained board recipes with the pinned AudioReach source.
  echo '${manifest.sha256}  ${audio}/${manifest.archive}' | sha256sum -c -
  tar -xzf ${audio}/${manifest.archive}
  m4 -I ${audio} -I ${manifest.directory} \
    ${audio}/OnePlus-Pad-2-Pro.m4 > topology.conf
  mkdir -p $out/lib/firmware/qcom/sm8750 $out/share/alsa
  alsatplg -c topology.conf \
    -o $out/lib/firmware/qcom/sm8750/OnePlus-Pad-2-Pro-tplg.bin
  alsatplg -d $out/lib/firmware/qcom/sm8750/OnePlus-Pad-2-Pro-tplg.bin \
    -o decoded.conf

  # Keep all generic cards and UCM includes available, including USB audio.
  cp -r ${alsa-ucm-conf}/share/alsa/ucm2 $out/share/alsa/
  chmod -R u+w $out/share/alsa/ucm2
  cp -r ${audio}/ucm2/. \
    $out/share/alsa/ucm2/

  rotation=${audio}/speaker-rotation
  install -Dm644 "$rotation/55-erhai-speaker-rotation.conf" \
    "$out/share/pipewire/pipewire.conf.d/55-erhai-speaker-rotation.conf"
  for context in client pipewire-pulse; do
    install -Dm644 "$rotation/50-erhai-speaker-upmix.conf" \
      "$out/share/pipewire/$context.conf.d/50-erhai-speaker-upmix.conf"
  done

  mkdir -p $out/share/doc/erhai-audio
  cp ${manifest.directory}/LICENSE.BSD-3-Clause $out/share/doc/erhai-audio/
  cp ${audio}/source.json $out/share/doc/erhai-audio/
  cp ${audio}/LICENSE.BSD-3-Clause $out/share/doc/erhai-audio/BOARD-LICENSE
''
