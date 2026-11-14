#!/usr/bin/env bash
# Read-only Pad 2 Pro monitor. Power: Bash/awk/coreutils. Display: GNOME D-Bus,
# loginctl, journalctl, grep; root can also read the DRM scanout format.
set -u

battery=/sys/class/power_supply/qcom-battmgr-bat
usb=/sys/class/power_supply/qcom-battmgr-usb
backlight=/sys/class/backlight/backlight
hwmon=/sys/class/hwmon
interval=1
display_connector=DSI-1
limit=0
csv=0
interactive=0

usage() {
    cat <<'EOF'
Usage: power-top.sh [options]
  -i, --interval SECONDS  Refresh interval (default: 1)
  -n, --count NUMBER      Exit after NUMBER samples
      --once             Print one snapshot
      --csv              Write CSV instead of the dashboard
      --battery PATH     Battery power_supply directory
      --usb PATH         Measured USB power_supply directory (not UCSI)
      --backlight PATH   Backlight directory
      --hwmon PATH       hwmon class directory (default: /sys/class/hwmon)
      --display NAME     Connector to inspect (default: DSI-1)
  -h, --help             Show this help

Interactive keys: q = quit, r = reset averages, space = pause/resume.
Examples:
  ./power-top.sh
  ./power-top.sh --once
  ./power-top.sh --csv -n 120 > hdr12-power.csv

current_now is in microamps; voltage_now is in microvolts.
Power is calculated as V * I. Battery sign follows the current driver.
HDR comes from the active GNOME session. Color is the compositor/output path,
not the bit depth of an application image. Unverified state is N/A, not 12-bit.
Full scanout detection may require root access to /sys/kernel/debug/dri.
Temperatures use standard hwmon inputs (millidegrees C); groups show maxima.
Important temperature inputs are sampled at most once per second.
CPU 0..5 belong to cluster 0, CPU 6..7 to cluster 1; each uses its hotter sensor.
Battery power_supply temperature uses tenths of a degree C instead.
The tool never writes sysfs or changes display/charging settings.
EOF
}

fail() { printf '%s\n' "$*" >&2; exit 2; }
while (($#)); do
    case $1 in
        -h|--help) usage; exit 0 ;;
        --once) limit=1; shift ;;
        --csv) csv=1; shift ;;
        -i|--interval|-n|--count|--battery|--usb|--backlight|--display|--hwmon)
            (($# >= 2)) || fail "Missing value for $1"
            case $1 in
                -i|--interval) interval=$2 ;;
                -n|--count) limit=$2 ;;
                --battery) battery=$2 ;;
                --usb) usb=$2 ;;
                --backlight) backlight=$2 ;;
                --hwmon) hwmon=$2 ;;
                --display) display_connector=$2 ;;
            esac
            shift 2 ;;
        *) fail "Unknown option: $1 (see --help)" ;;
    esac
done
[[ $interval =~ ^([0-9]+([.][0-9]+)?|[.][0-9]+)$ ]] || fail 'Invalid interval'
awk -v n="$interval" 'BEGIN { exit !(n > 0) }' || fail 'Interval must be positive'
[[ $limit =~ ^[0-9]+$ ]] || fail 'Count must be a nonnegative integer'
limit=$((10#$limit))
thermal_last_us=0

# Missing/unreadable attributes stay N/A, including errors during hot unplug.
read_attr() {
    local destination=$1 path=$2 value
    if { [[ -r $path ]] && IFS= read -r value < "$path"; } 2>/dev/null; then
        printf -v "$destination" '%s' "$value"
    else
        printf -v "$destination" '%s' 'N/A'
    fi
}
integer() { [[ $1 =~ ^-?[0-9]+$ ]]; }

# Discover important sensors by name: hwmon numbers can change after rebind.
# Use Bash reads and the existing frame formatter to avoid one process/sensor.
query_temperatures() {
    local chip name input sensor_value group core cluster member now_us
    now_us=${EPOCHREALTIME/./}
    ((now_us - thermal_last_us >= 1000000)) || return 0
    thermal_last_us=$now_us
    read_attr temperature "$battery/temp"
    thermal_readings=
    for chip in "$hwmon"/hwmon*; do
        [[ -d $chip ]] || continue
        read_attr name "$chip/name"
        [[ $name != N/A ]] || continue
        core=-1
        case $name in
            gpuss[0-9]*_thermal) group=GPU ;;
            qcom_battmgr_bat) group=Battery ;;
            skin_thermal) group=Skin ;;
            ddr_thermal) group=DDR ;;
            ath12k_hwmon) group=Wi-Fi ;;
            pm8550*|pmih0108*) group=PMIC ;;
            cpuss_*_thermal) group=CPU-SS ;;
            *) group= ;;
        esac
        if [[ $name =~ ^cpu_([01])_([0-5])_[01]_thermal$ ]]; then
            cluster=${BASH_REMATCH[1]}; member=${BASH_REMATCH[2]}
            if ((cluster == 0 || member < 2)); then
                group=CPU; core=$((cluster * 6 + member))
            fi
        fi
        [[ -n $group ]] || continue
        for input in "$chip"/temp*_input; do
            [[ -e $input ]] || continue
            read_attr sensor_value "$input"
            integer "$sensor_value" || sensor_value=N/A
            thermal_readings+="$group|$core|$name|${input##*/}|$sensor_value"$'\n'
        done
    done
}

# Parse only the requested physical monitor and its CURRENT mode. Supported
# HDR modes, other outputs and non-current refresh rates must not count.
parse_display_state() {
    awk -v connector="$display_connector" '
        BEGIN { q = sprintf("%c", 39); hdr = hz = mode = "N/A" }
        {
            n = split($0, monitors, "\\(\\(" q)
            for (i = 2; i <= n; i++) {
                if (index(monitors[i], connector q ",") != 1) continue
                text = monitors[i]
                pattern = q "color-mode" q ":[[:space:]]*<uint32 [0-9]+>"
                if (match(text, pattern)) {
                    v = substr(text, RSTART, RLENGTH)
                    sub(/.*<uint32 /, "", v); sub(/>.*/, "", v)
                    if (v == 1) hdr = "ON"
                    else if (v == 0 || v == 2) hdr = "OFF"
                }
                count = split(text, modes, "\\(" q)
                for (j = 2; j <= count; j++) {
                    if (modes[j] !~ (q "is-current" q ":[[:space:]]*<true>")) continue
                    split(modes[j], fields, ",")
                    mode = fields[1]; sub(q ".*", "", mode)
                    hz = fields[4]; gsub(/[[:space:]]/, "", hz)
                    break
                }
                break
            }
        }
        END { print hdr "|" hz "|" mode }'
}

# Only call a 10-bit buffer + the board 8-bpc dither policy "8+2-bit".
# A capable binary by itself is insufficient evidence that FRC is enabled.
classify_color() {
    local hdr=$1 hz=$2 format=$3 frc=$4 dither=$5 awake=$6
    if [[ $awake == OFF ]]; then printf 'IDLE'; return; fi
    if [[ $hdr == N/A ]]; then printf 'N/A'; return; fi
    if [[ $hz =~ ^[0-9]+([.][0-9]+)?$ ]] &&
        awk -v hz="$hz" 'BEGIN { exit !(hz < 100) }'; then
        frc=no
    fi
    if [[ $hdr == ON && $frc == yes && $hz =~ ^[0-9]+([.][0-9]+)?$ ]] &&
        awk -v hz="$hz" 'BEGIN { exit !(hz >= 100) }'; then
        case $format in
            XR30|XB30|AR30|AB30|N/A) printf '8+4-bit'; return ;;
        esac
    fi
    case $format in
        XR30|XB30|AR30|AB30)
            if [[ $hdr == ON && $frc != no ]]; then printf 'N/A'
            elif [[ $dither == yes ]]; then printf '8+2-bit'
            else printf '10-bit-buffer'; fi ;;
        XR24|XB24|AR24|AB24) printf '8-bit' ;;
        *) printf 'N/A' ;;
    esac
}

display_bus=()
display_pid=
frc_capable=unknown
frc_runtime=unknown
display_tick=-1
display_key=
hdr=N/A
refresh=N/A
display_mode=N/A
scanout=N/A
color=N/A
display_note='GNOME display state unavailable'

display_call() {
    timeout 2 "${display_bus[@]}" "$@" 2>/dev/null
}

query_display() {
    local session info key value reply pid library probe_key event card awake
    local frc_gate=present disabled_receipt= process_start= receipt_pid= receipt_start= disabled_ticks=
    local adaptive_state= expected_hdr=
    # Limit D-Bus/process inspection to once per second at fast power intervals.
    ((SECONDS != display_tick)) || return
    display_tick=$SECONDS
    hdr=N/A; refresh=N/A; display_mode=N/A; scanout=N/A; color=N/A
    display_note='GNOME display state unavailable'
    if ! command -v gdbus >/dev/null || ! command -v timeout >/dev/null; then
        display_note='gdbus/timeout unavailable'; return
    fi
    if ((${#display_bus[@]} == 0)); then
        display_uid=$UID
        display_user=
        if ((UID == 0)); then
            session=$(timeout 2 loginctl show-seat seat0 -p ActiveSession --value 2>/dev/null) || return
            [[ -n $session ]] || return
            info=$(timeout 2 loginctl show-session "$session" -p User -p Name 2>/dev/null) || return
            while IFS='=' read -r key value; do
                case $key in User) display_uid=$value ;; Name) display_user=$value ;; esac
            done <<< "$info"
            [[ $display_uid =~ ^[0-9]+$ && -n $display_user ]] || return
        fi
        [[ -S /run/user/$display_uid/bus ]] || return
        display_bus=(env "XDG_RUNTIME_DIR=/run/user/$display_uid"
            "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$display_uid/bus"
            gdbus call --session)
        if ((UID == 0 && display_uid != 0)); then
            display_bus=(runuser -u "$display_user" -- "${display_bus[@]}")
        fi
    fi
    reply=$(display_call --dest org.gnome.Mutter.DisplayConfig \
        --object-path /org/gnome/Mutter/DisplayConfig \
        --method org.gnome.Mutter.DisplayConfig.GetCurrentState) || {
        display_bus=(); return
    }
    IFS='|' read -r hdr refresh display_mode < <(printf '%s\n' "$reply" | parse_display_state)
    [[ $hdr != N/A ]] || { display_note="GNOME has no current state for $display_connector"; return; }
    pid=$(display_call --dest org.freedesktop.DBus \
        --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.GetConnectionUnixProcessID org.gnome.Mutter.DisplayConfig)
    pid=${pid#*uint32 }; pid=${pid%%,*}
    if [[ $pid =~ ^[0-9]+$ && $pid != "$display_pid" ]]; then
        display_pid=$pid; frc_capable=unknown; frc_runtime=unknown
        library=$(awk '/libmutter-clutter/ {print $NF; exit}' "/proc/$pid/maps" 2>/dev/null)
        if [[ -r $library ]]; then
            if LC_ALL=C grep -aFq 'clutter_stage_view_enable_output_frc' "$library"; then
                frc_capable=yes
            else
                frc_capable=no
            fi
        fi
    elif [[ ! $pid =~ ^[0-9]+$ ]]; then
        display_pid=; frc_capable=unknown; frc_runtime=unknown
    fi
    # A temporary comparison can remove the gate and rebuild the stage views
    # without restarting GNOME. Historical FRC messages then describe old views.
    # The receipt also covers processes started after that rebuild: every new
    # view reads the absent gate. The switch helper invalidates the receipt
    # before restoring the gate. Absence alone does not prove FRC is disabled.
    if [[ ! -f /etc/mutter/xn242-output-frc ]]; then
        frc_gate=absent
        disabled_receipt=/run/pad2pro-precision-test/frc-disabled
        if [[ -n $display_pid && -f $disabled_receipt && ! -L $disabled_receipt &&
              $(stat -c '%u:%a' "$disabled_receipt" 2>/dev/null) == 0:644 ]]; then
            read -r receipt_pid receipt_start disabled_ticks < "$disabled_receipt" || :
            process_start=$(sed 's/.*) //' "/proc/$display_pid/stat" 2>/dev/null | awk '{print $20}')
            if [[ $process_start =~ ^[0-9]+$ ]]; then
                if [[ $receipt_pid == "$display_pid" && $receipt_start =~ ^[0-9]+$ &&
                      $receipt_start == "$process_start" ]]; then
                    frc_gate=disabled-confirmed
                elif [[ $disabled_ticks =~ ^[0-9]+$ ]] && ((process_start > disabled_ticks)); then
                    frc_gate=disabled-confirmed
                fi
            fi
        fi
    fi
    probe_key="$display_pid|$hdr|$refresh|$frc_gate"
    if [[ $probe_key != "$display_key" || $frc_runtime == unknown ]]; then
        display_key=$probe_key
        frc_runtime=unknown
        if [[ $hdr == OFF || $frc_capable == no || $frc_gate == disabled-confirmed ]]; then
            frc_runtime=no
        elif [[ $frc_gate == present && $frc_capable == yes && $display_pid =~ ^[0-9]+$ ]]; then
            event=$(timeout 2 journalctl -b "_PID=$display_pid" -o cat --no-pager \
                --grep='XN242 HDR output:' -n 1 2>/dev/null)
            [[ $event == *'8+4-bit FRC,'* ]] && frc_runtime=yes
        fi
    fi
    # The primary plane of this connector, not a cursor/another display.
    for card in /sys/class/drm/card*-"$display_connector"; do
        [[ -e $card ]] || continue
        card=${card##*/}; card=${card%%-*}; card=${card#card}
        scanout=$(awk -v connector="$display_connector" '
            /^plane\[/ {p=$0; in_plane=1; in_connector=0; next}
            /^crtc\[/ {in_plane=0; in_connector=0}
            /^connector\[/ {
                in_plane=0; in_connector=($NF == connector); next
            }
            in_plane && /^[[:space:]]*crtc=/ {sub(/.*crtc=/, ""); crtc[p]=$0}
            in_plane && /^[[:space:]]*format=/ {sub(/.*format=/, ""); split($0,a," "); fmt[p]=a[1]}
            in_plane && /normalized-zpos=/ {sub(/.*=/, ""); z[p]=$0}
            in_connector && /^[[:space:]]*crtc=/ {sub(/.*crtc=/, ""); target=$0}
            END {
                best=100000; result="N/A"
                for (p in fmt) if (target != "(null)" && crtc[p] == target && z[p]+0 < best) {
                    best=z[p]+0; result=fmt[p]
                }
                print result
            }' "/sys/kernel/debug/dri/$card/state" 2>/dev/null)
        [[ -n $scanout ]] || scanout=N/A
        break
    done
    awake=UNKNOWN
    if integer "$bl_power"; then
        if [[ $bl_power != 0 || $actual == 0 ]]; then awake=OFF; else awake=ON; fi
    fi
    dither=no
    [[ -e /sys/firmware/devicetree/base/soc@0/display-subsystem@ae00000/dsi@ae94000/panel@0/qcom,dpu-8bpc-dither ]] && dither=yes
    if [[ $display_connector != DSI-1 ]]; then
        color=N/A; display_note='8+2/8+4 policy applies to XN242 DSI-1'; return
    fi
    # New compositor API describes the actual live view, across precision
    # changes and compositor restarts, and is readable without DRM privileges.
    adaptive_state=$(display_call --dest org.gnome.Mutter.Xn242 \
        --object-path /org/gnome/Mutter/Xn242 --method org.gnome.Mutter.Xn242.GetState) || :
    case $hdr in ON) expected_hdr=true ;; OFF) expected_hdr=false ;; esac
    if [[ -n $display_pid && -n $expected_hdr &&
          $adaptive_state == *"'connector': <'DSI-1'>"* &&
          $adaptive_state == *"'compositor-pid': <uint32 $display_pid>"* &&
          $adaptive_state == *"'hdr': <$expected_hdr>"* ]]; then
        if [[ $awake == OFF ]]; then
            color=IDLE; display_note='display off; no active scanout'; return
        elif [[ $hdr == ON && $adaptive_state == *"'precision': <uint32 12>"* ]]; then
            color=8+4-bit; display_note='running compositor confirms 12-bit equivalent FRC'; return
        elif [[ $adaptive_state == *"'precision': <uint32 10>"* ]]; then
            color=8+2-bit; display_note='running compositor confirms 10-bit output with board dithering'; return
        fi
    fi
    color=$(classify_color "$hdr" "$refresh" "$scanout" "$frc_runtime" "$dither" "$awake")
    case $color in
        8+4-bit) display_note='8+4 FRC confirmed in the running compositor' ;;
        8+2-bit) display_note='10-bit scanout + board 8-bpc output dithering' ;;
        IDLE) display_note='display off; no active scanout' ;;
        8-bit|10-bit-buffer) display_note='scanout format confirmed; no 8+4 FRC' ;;
        *) display_note='precision unverified (DRM access/FRC evidence unavailable)' ;;
    esac
}

cleanup() {
    if ((interactive)); then
        printf '\033[?25h\033[?1049l'
        exec 3<&-
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

if ((csv == 0 && limit != 1)) && [[ -t 0 && -t 1 && ${TERM:-dumb} != dumb ]]; then
    if { exec 3</dev/tty; } 2>/dev/null; then
        interactive=1
        printf '\033[?1049h\033[?25l'
    fi
fi

if ((csv)); then
    printf '%s\n' 'timestamp,elapsed_s,sample,battery_status,battery_capacity_pct,battery_temp_c,battery_voltage_v,battery_current_a,battery_power_w,usb_online,usb_voltage_v,usb_current_a,usb_power_w,backlight_set,backlight_actual,backlight_max,backlight_bl_power,display_connector,hdr,color_path,refresh_hz,scanout_format,display_evidence,cpu_temp_c,gpu_temp_c,sensor_battery_temp_c,skin_temp_c,ddr_temp_c,wifi_temp_c,pmic_temp_c,cpuss_temp_c,aoss_temp_c,modem_temp_c,camera_temp_c,video_temp_c,npu_temp_c,xo_temp_c,gpio2_temp_c,other_temp_c,cpu0_temp_c,cpu1_temp_c,cpu2_temp_c,cpu3_temp_c,cpu4_temp_c,cpu5_temp_c,cpu6_temp_c,cpu7_temp_c,temperature_sensor_count'
fi

sample=0
sum_bat=0
sum_usb=0
count_bat=0
count_usb=0
paused=0
started=$SECONDS
while :; do
    if ((paused == 0)); then
        read_attr bv "$battery/voltage_now"
        read_attr bi "$battery/current_now"
        read_attr bs "$battery/status"
        read_attr capacity "$battery/capacity"
        read_attr uv "$usb/voltage_now"
        read_attr ui "$usb/current_now"
        read_attr online "$usb/online"
        read_attr brightness "$backlight/brightness"
        read_attr actual "$backlight/actual_brightness"
        read_attr maximum "$backlight/max_brightness"
        read_attr bl_power "$backlight/bl_power"
        query_temperatures
        query_display
        bp=N/A
        up=N/A
        # Accumulate micro-watts, not products of micro-units, to avoid
        # overflowing the running sums during long monitoring sessions.
        if integer "$bv" && integer "$bi"; then
            bp=$((bv * bi / 1000000))
            sum_bat=$((sum_bat + bp))
            count_bat=$((count_bat + 1))
        fi
        if [[ $online == 1 ]] && integer "$uv" && integer "$ui"; then
            up=$((uv * ui / 1000000))
            sum_usb=$((sum_usb + up))
            count_usb=$((count_usb + 1))
        fi
        sample=$((sample + 1))
    fi
    printf -v timestamp '%(%Y-%m-%dT%H:%M:%S%z)T' -1
    frame=$(awk -v csv="$csv" -v ts="$timestamp" -v elapsed="$((SECONDS - started))" \
        -v sample="$sample" -v interval="$interval" -v paused="$paused" \
        -v bv="$bv" -v bi="$bi" -v bp="$bp" -v bs="$bs" \
        -v capacity="$capacity" -v temperature="$temperature" \
        -v uv="$uv" -v ui="$ui" -v up="$up" -v online="$online" \
        -v brightness="$brightness" -v actual="$actual" -v maximum="$maximum" \
        -v bl_power="$bl_power" -v sum_bat="$sum_bat" -v sum_usb="$sum_usb" \
        -v connector="$display_connector" -v hdr="$hdr" -v color="$color" \
        -v refresh="$refresh" -v scanout="$scanout" -v display_note="$display_note" \
        -v thermal_readings="$thermal_readings" \
        -v count_bat="$count_bat" -v count_usb="$count_usb" '
        function numeric(v) { return v ~ /^-?[0-9]+$/ }
        function scaled(v, factor, format) {
            return numeric(v) ? sprintf(format, v / factor) : "N/A"
        }
        function field(v) {
            gsub(/"/, "\"\"", v)
            return "\"" v "\""
        }
        function group_temperature(group) {
            return group in hottest ? sprintf("%.1f", hottest[group] / 1000) : "N/A"
        }
        function core_temperature(core) {
            return core in cores ? sprintf("%.1f", cores[core] / 1000) : "N/A"
        }
        BEGIN {
            group_count = split("CPU GPU Battery Skin DDR Wi-Fi PMIC CPU-SS", groups, " ")
            channel_count = split(thermal_readings, channels, "\n")
            readable = 0
            for (i = 1; i <= channel_count; i++) {
                if (split(channels[i], sensor, "[|]") != 5 || !numeric(sensor[5])) continue
                group = sensor[1]; core = sensor[2]; value = sensor[5] + 0
                readable++
                if (!(group in hottest) || value > hottest[group]) hottest[group] = value
                if (group == "CPU" && core >= 0 && core < 8)
                    if (!(core in cores) || value > cores[core]) cores[core] = value
            }
            if (csv) {
                printf "%s,%d,%d,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s", \
                    ts, elapsed, sample, field(bs), capacity, \
                    scaled(temperature, 10, "%.1f"), \
                    scaled(bv, 1000000, "%.6f"), scaled(bi, 1000000, "%.6f"), \
                    scaled(bp, 1000000, "%.6f"), online, \
                    online == 1 ? scaled(uv, 1000000, "%.6f") : "N/A", \
                    online == 1 ? scaled(ui, 1000000, "%.6f") : "N/A", \
                    scaled(up, 1000000, "%.6f"), brightness, actual, maximum, bl_power
                printf ",%s,%s,%s,%s,%s,%s", field(connector), hdr, color, refresh, scanout, field(display_note)
                for (i = 1; i <= group_count; i++) printf ",%s", group_temperature(groups[i])
                # Preserve existing CSV columns for the omitted minor regions.
                for (i = 0; i < 8; i++) printf ",N/A"
                for (i = 0; i < 8; i++) printf ",%s", core_temperature(i)
                printf ",%d\n", readable
                exit
            }
            printf "power-top  %s  refresh=%ss  sample=%d%s\n\n", \
                ts, interval, sample, paused ? "  [PAUSED]" : ""
            printf "%-9s %-14s %11s %13s %12s %12s\n", \
                "SOURCE", "STATUS", "VOLTAGE(V)", "CURRENT(mA)", "POWER(W)", "MEAN(W)"
            printf "%-9s %-14s %11s %13s %12s %12s\n", "Battery", bs, \
                scaled(bv, 1000000, "%.3f"), scaled(bi, 1000, "%+.1f"), \
                scaled(bp, 1000000, "%+.3f"), \
                count_bat ? sprintf("%+.3f", sum_bat / count_bat / 1000000) : "N/A"
            state = online == 1 ? "Online" : (online == 0 ? "Offline" : "N/A")
            printf "%-9s %-14s %11s %13s %12s %12s\n", "USB", state, \
                online == 1 ? scaled(uv, 1000000, "%.3f") : "N/A", \
                online == 1 ? scaled(ui, 1000, "%.1f") : "N/A", \
                scaled(up, 1000000, "%.3f"), \
                count_usb ? sprintf("%.3f", sum_usb / count_usb / 1000000) : "N/A"
            light_state = "N/A"
            if (numeric(bl_power))
                light_state = bl_power != 0 || actual == "0" ? "OFF" : "ON"
            printf "\nBacklight: set=%s  actual=%s  max=%s  [%s]\n", \
                brightness, actual, maximum, light_state
            printf "Battery: capacity=%s%%  temperature=%s C\n", \
                capacity, scaled(temperature, 10, "%.1f")
            printf "Display: %s  HDR=%s  Color=%s  Hz=%s  Scanout=%s\n", \
                connector, hdr, color, refresh == "N/A" ? "N/A" : sprintf("%.2f", refresh), scanout
            printf "  %s\n", display_note
            printf "\nKey temperatures (C; highest per group, %d readable channels):\n", readable
            for (i = 1; i <= group_count; i++) {
                printf "%-7s %5s%s", groups[i], group_temperature(groups[i]), i % 4 ? "   " : "\n"
            }
            printf "CPU cores:"
            for (i = 0; i < 8; i++) printf "  %d:%s", i, core_temperature(i)
            printf "\n"
            printf "Averages: %d battery / %d USB samples; elapsed=%ds\n\n", \
                count_bat, count_usb, elapsed
            print "电池功率保留电流符号：当前驱动正数=充入，负数=放出。"
            print "功率由 V × I 计算；USB 输入还包含充电与转换损耗。"
            print "背光实际值是驱动码值，不是电流、功率或 nit。"
            print "切换显示模式后，可按 r 清零平均功率。"
            print "q: quit   r: reset averages   Space: pause/resume"
        }')
    if ((interactive)); then
        # Clear each line after replacing its contents, including shorter
        # values after unplug/reset, without blanking the whole screen.
        printf '\033[H%s\033[J' "${frame//$'\n'/$'\033[K\n'}"
    else
        printf '%s\n' "$frame"
    fi
    ((limit > 0 && sample >= limit)) && break
    if ((interactive)); then
        key=
        IFS= read -r -s -n 1 -t "$interval" key <&3 || :
        case $key in
            q|Q) break ;;
            r|R)
                sum_bat=0; sum_usb=0; count_bat=0; count_usb=0
                sample=0; started=$SECONDS; paused=0 ;;
            ' ') paused=$((1 - paused)) ;;
        esac
    else
        sleep "$interval" || break
    fi
done
