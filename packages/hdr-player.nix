{ symlinkJoin, writeShellApplication, mpv, glib }:
let
  launcher = writeShellApplication {
    name = "pad2pro-hdr-player";
    text = ''
      exec ${mpv}/bin/mpv --include=${./hdr-player.conf} --profile=pad2pro-hdr "$@"
    '';
  };
  nativeLauncher = writeShellApplication {
    name = "pad2pro-native-hdr-player";
    text = ''
      exec ${mpv}/bin/mpv --include=${./hdr-player.conf} --profile=pad2pro-native-hdr "$@"
    '';
  };
  autoLauncher = writeShellApplication {
    name = "pad2pro-video-player";
    runtimeInputs = [ glib ];
    text = ''
      state=$(gdbus call --session --dest org.gnome.Mutter.Xn242 \
        --object-path /org/gnome/Mutter/Xn242 \
        --method org.gnome.Mutter.Xn242.GetState 2>/dev/null) || state=
      if [[ $state == *"'hdr': <true>"* ]]; then
        exec ${nativeLauncher}/bin/pad2pro-native-hdr-player "$@"
      else
        exec ${launcher}/bin/pad2pro-hdr-player "$@"
      fi
    '';
  };
in symlinkJoin {
  name = "pad2pro-hdr-player-${mpv.version}";
  paths = [ mpv launcher nativeLauncher autoLauncher ];
  postBuild = ''
    # Keep the upstream application identity and file associations. Profile
    # selection belongs inside the player, not in separate application entries.
    rm $out/share/applications/mpv.desktop
    rm -f $out/share/applications/umpv.desktop
    cp ${mpv}/share/applications/mpv.desktop $out/share/applications/mpv.desktop
    chmod u+w $out/share/applications/mpv.desktop
    substituteInPlace $out/share/applications/mpv.desktop \
      --replace-fail "Exec=mpv " "Exec=${autoLauncher}/bin/pad2pro-video-player "
  '';
}
