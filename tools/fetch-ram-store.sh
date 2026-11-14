set -eu
expected=
for argument in $(cat /proc/cmdline); do
  case "$argument" in
    pad2pro.ram.sha256=*)
      [ -z "$expected" ] || { echo 'Duplicate RAM image digest' >&2; exit 1; }
      expected=${argument#pad2pro.ram.sha256=}
      ;;
  esac
done
case "$expected" in
  *[!0-9a-f]*|'') echo 'Missing/invalid RAM image SHA-256' >&2; exit 1 ;;
esac
[ "${#expected}" = 64 ] || { echo 'Invalid RAM image digest length' >&2; exit 1; }
# Bounded retries allow the PC to finish configuring its newly enumerated USB
# interface. The downloaded store remains in initrd RAM through switch-root.
curl --fail --noproxy '*' --retry 30 --retry-all-errors --retry-delay 1 \
  --connect-timeout 3 --max-time 180 \
  "http://192.168.77.10:8000/rootfs-$expected.squashfs" -o /nix-store.squashfs.partial
printf '%s  %s\n' "$expected" /nix-store.squashfs.partial | sha256sum -c -
mv /nix-store.squashfs.partial /nix-store.squashfs
