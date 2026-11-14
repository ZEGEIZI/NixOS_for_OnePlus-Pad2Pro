set -eu
gadget=/sys/kernel/config/usb_gadget/nixos
if [ -d "$gadget" ]; then
  echo "Existing NixOS USB gadget; refusing to replace it" >&2
  exit 1
fi
set -- /sys/class/udc/*
[ "$#" = 1 ] && [ -e "$1" ] || { echo 'Expected exactly one USB controller' >&2; exit 1; }
controller=${1##*/}
mkdir "$gadget"
cd "$gadget"
echo 0x1d6b > idVendor
echo 0x0104 > idProduct
mkdir strings/0x409
echo 'NixOS' > strings/0x409/manufacturer
echo 'OnePlus Pad 2 Pro NCM' > strings/0x409/product
mkdir configs/c.1
mkdir functions/ncm.usb0
# Stable, local addresses derived at runtime; no per-unit identifiers in the store.
identity=/etc/machine-id
[ -s "$identity" ] || identity=/proc/sys/kernel/random/boot_id
digest=$(sha256sum "$identity")
digest=${digest%% *}
mac=$(printf '%s' "$digest" | cut -c1-10 | sed 's/../:&/g')
echo "02$mac" > functions/ncm.usb0/dev_addr
echo "06$mac" > functions/ncm.usb0/host_addr
ln -s functions/ncm.usb0 configs/c.1/
echo "$controller" > UDC
