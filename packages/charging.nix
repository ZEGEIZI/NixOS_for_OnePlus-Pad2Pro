{ lib, stdenvNoCC, python3, glib, gobject-introspection, wrapGAppsNoGuiHook, gnome-shell }:
let
  python = python3.withPackages (ps: [ ps.pygobject3 ps.pyudev ]);
  shellVersion = lib.versions.major gnome-shell.version;
in stdenvNoCC.mkDerivation {
  pname = "erhai-charging-desktop";
  version = "0.10.2";
  src = ./charging;
  nativeBuildInputs = [ glib wrapGAppsNoGuiHook gobject-introspection ];
  buildInputs = [ glib ];
  dontBuild = true;
  installPhase = ''
    runHook preInstall
    mkdir -p $out/libexec $out/share/tablet-charge $out/share/doc/erhai-charging
    cp libexec/tablet-charge-* $out/libexec/
    printf 'erhai\n' > $out/share/tablet-charge/device
    for program in $out/libexec/tablet-charge-*; do
      substituteInPlace "$program" \
        --replace-fail '#!/usr/bin/python3' '#!${python}/bin/python3'
    done
    substituteInPlace $out/libexec/tablet-charge-display $out/libexec/tablet-charge-idle \
      --replace-fail '/usr/share/tablet-charge/device' "$out/share/tablet-charge/device"
    chmod +x $out/libexec/tablet-charge-*

    extension=$out/share/gnome-shell/extensions/charge-indicator@tablet-linux
    mkdir -p "$extension/schemas"
    cp extension/* "$extension/"
    cp schemas/* "$extension/schemas/"
    glib-compile-schemas --strict "$extension/schemas"
    substituteInPlace "$extension/extension.js" \
      --replace-fail '/usr/libexec/tablet-charge-display' "$out/libexec/tablet-charge-display" \
      --replace-fail '/usr/libexec/tablet-charge-behaviour' "$out/libexec/tablet-charge-behaviour"
    mkdir -p "$out/share/polkit-1/actions"
    cat > "$out/share/polkit-1/actions/org.tablet.charge-behaviour.policy" <<POLICY
    <?xml version="1.0" encoding="UTF-8"?>
    <policyconfig>
      <action id="org.tablet.charge-behaviour">
        <description>Control the built-in battery charging mode</description>
        <message>Control battery charging</message>
        <defaults><allow_any>no</allow_any><allow_inactive>no</allow_inactive><allow_active>yes</allow_active></defaults>
        <annotate key="org.freedesktop.policykit.exec.path">$out/libexec/tablet-charge-behaviour</annotate>
      </action>
    </policyconfig>
    POLICY
    substituteInPlace "$extension/metadata.json" \
      --replace-fail '["50"]' '["${shellVersion}"]'
    cp upstream-source.json LICENSE $out/share/doc/erhai-charging/
    runHook postInstall
  '';
  # The sampler is also loaded by runpy from the display helper's directory.
  # Keep it unwrapped so runpy sees Python rather than a shell wrapper.
  preFixup = ''
    gappsWrapperArgs+=(--prefix GI_TYPELIB_PATH : "${glib.out}/lib/girepository-1.0")
    wrapGApp $out/libexec/tablet-charge-idle
  '';
  dontWrapGApps = true;
  passthru.extensionUuid = "charge-indicator@tablet-linux";
  meta = {
    description = "GNOME charging power indicator and wired charging suspend policy";
    license = lib.licenses.mit;
    platforms = lib.platforms.linux;
  };
}
