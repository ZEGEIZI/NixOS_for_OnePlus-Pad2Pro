#!/usr/bin/env bash
# Session control for the compositor, including from root SSH.
set -euo pipefail
case ${1:-status} in
    10|12|status) action=${1:-status} ;;
    *) echo 'Usage: pad2pro-display [10|12|status]' >&2; exit 2 ;;
esac
bus=(gdbus call --session)
if ((EUID == 0)); then
    session=$(loginctl show-seat seat0 -p ActiveSession --value)
    display_uid=$(loginctl show-session "$session" -p User --value)
    display_user=$(loginctl show-session "$session" -p Name --value)
    [[ $display_uid =~ ^[0-9]+$ && -n $display_user ]]
    bus=(runuser -u "$display_user" -- env "XDG_RUNTIME_DIR=/run/user/$display_uid"
         "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$display_uid/bus" gdbus call --session)
fi
args=(--dest org.gnome.Mutter.Xn242 --object-path /org/gnome/Mutter/Xn242 --method)
if [[ $action != status ]]; then
    "${bus[@]}" "${args[@]}" org.gnome.Mutter.Xn242.SetPrecision "$action"
fi
"${bus[@]}" "${args[@]}" org.gnome.Mutter.Xn242.GetState
