# Called by the optional USB diagnostic HTTP servers. Reads a fixed set of files;
# never evaluates query parameters or writes a hardware/sysfs attribute.
set -eu
printf 'Content-Type: text/plain\r\n\r\n'
echo NIXOS_PAD2PRO_LIVE_STATUS_v2
uname -r
cat /proc/uptime
echo '[system identity]'
cat /proc/cmdline
for link in /run/booted-system /run/current-system; do
  if [ -e "$link" ]; then printf '%s=' "$link"; readlink -f "$link"; fi
done
if command -v systemctl >/dev/null 2>&1; then
  echo '[failed units]'
  systemctl --failed --no-pager --plain || true
fi
echo '[mounts]'
# Report PID 1's mounts, including when the HTTP service has a private sandbox.
findmnt -N 1 -rn -o SOURCE,FSTYPE,TARGET,OPTIONS
echo '[block devices]'
lsblk -o NAME,SIZE,TYPE,FSTYPE,PARTLABEL,MOUNTPOINTS
echo '[USB state]'
for state in /sys/class/udc/*/state /sys/class/usb_role/*/role; do
  [ -r "$state" ] || continue
  printf '%s=' "$state"
  cat "$state"
done

read_field() {
  if [ -r "$1/$2" ]; then
    printf '%s=' "$2"
    cat "$1/$2" || true
  fi
}

echo '[pen charger]'
read_field /sys/module/cps8601 version
for charger in /sys/bus/i2c/drivers/cps8601-pen-charger/*-*; do
  [ -d "$charger" ] || continue
  for field in fw_version present pen_soc; do
    read_field "$charger" "$field"
  done
done

echo '[cpu frequency]'
for policy in /sys/devices/system/cpu/cpufreq/policy*; do
  [ -d "$policy" ] || continue
  echo "${policy##*/}"
  for field in scaling_driver scaling_governor scaling_cur_freq scaling_min_freq scaling_max_freq cpuinfo_min_freq cpuinfo_max_freq related_cpus; do
    read_field "$policy" "$field"
  done
done

echo '[thermal zones]'
for zone in /sys/class/thermal/thermal_zone*; do
  [ -d "$zone" ] || continue
  printf '%s ' "${zone##*/}"
  read_field "$zone" type
  read_field "$zone" temp
done

echo '[power supplies]'
for supply in /sys/class/power_supply/*; do
  [ -d "$supply" ] || continue
  echo "${supply##*/}"
  for field in type online status capacity current_now voltage_now power_now temp usb_type; do
    read_field "$supply" "$field"
  done
done

echo '[framebuffers]'
for framebuffer in /sys/class/graphics/fb*; do
  [ -d "$framebuffer" ] || continue
  echo "${framebuffer##*/}"
  for field in name virtual_size bits_per_pixel; do
    read_field "$framebuffer" "$field"
  done
done
