# 从分区到安装 NixOS：本机操作教程

这台 OPD2413 已完成以下安装。当前正常使用无需重新分区、格式化或刷写。
本文解释重装/首次安装的完整顺序；其中 GPT、mkfs、Android 数据重建会清除数据，
不要在现有系统上从头重复执行。若只是要登录现有 NixOS，直接看最后一节。

重新安装当前版本时，按 [安装说明](INSTALL.md) 从当前源码导出新安装包，
[基础、Wi-Fi 和蓝牙固件](FIRMWARE.md) 已随仓库提供，无需额外准备。
2026-11-13 已清空电脑上的历史安装缓存、镜像及验收材料，不保留存档。
本文后续的镜像、缓存及文件服务路径均为构建后的示例，使用前须重新生成并准备材料。
第 5 节的 v7 路径属于历史首装示例，不能再直接使用；需统一替换为新导出包的
目录、文件服务 URL、签名公钥和系统路径。

## 1. 先认识三个不同的位置

| 位置 | 本机容量 | 内容 |
| --- | ---: | --- |
| Android `userdata` | 约 258.97 GiB | Android 应用、个人数据及其加密文件系统 |
| `KShinC_BOOT` | 1 GiB ext4 | Linux 的 `/boot`，保存每一代的内核、DTB、initramfs 和菜单条目 |
| `NixOS_Root` | 200 GiB Btrfs | NixOS 系统、Nix store、用户目录与日志 |
| Android `boot_a` | 96 MiB | Android 内核与 kShimC 启动菜单，本机仅修改此槽位 |

前两类 Linux 分区与 Android `boot_a` 是不同的分区。NixOS 的安装流程是：

```text
备份 → RAM 维护系统 → 核对并调整 GPT → 格式化 Linux 分区
→ 创建并挂载 Btrfs 子卷 → 导入 NixOS 闭包 → nixos-install
→ 发布 /boot 文件 → 临时测试 kShimC → 固化菜单 → 双系统验证
```

设备 bootloader 须已解锁。另一台平板、另一种存储容量或另一版 Android 固件，
都需要重新核对布局及原厂 boot；不能直接套用本机的 LBA、GUID 或镜像。

## 2. 准备电脑和安装材料

下面“电脑”命令在本项目目录执行：

```sh
cd /path/to/NixOS_for_OnePlus-Pad2Pro
```

重新构建后，下面的路径作为材料位置示例：

- `artifacts/nixos-pad2pro-menu-pagination-v3/boot.img`：与实机读回摘要一致的分页菜单镜像。
- `artifacts/nixos-pad2pro-ram-system-v2/packed/boot.img`：完整 RAM 维护镜像。
- `artifacts/nixos-pad2pro-ram-system-v2/rootfs.squashfs`：v2 配套内存系统文件，须在电脑文件服务目录建立对应的哈希文件名链接。

上述文件当前均未保留，须先按构建说明重新生成。

v2 采用 USB 免密码 root 登录和本地自动登录，不需要个人 SSH 登录密钥。
v1 是早期密钥版；本文后续使用 v2，已安装的普通 NixOS 账户仍保持锁定。

普通安装包包含本机 boot PARTUUID。新建 GUID、换设备或更新固件时，须按
[安装说明](INSTALL.md) 重新配置及构建，不能继续使用本机材料。

**完整 RAM 维护镜像需要从电脑下载配套文件。单独执行 `fastboot boot` 不足以进入系统。**
下面的 USB 网络配置和 HTTP 服务必须先准备好，文件服务终端须一直保持运行。
下载仅使用 USB 局域网，不要求平板连接互联网。

RAM 系统的电脑 USB 地址为 `192.168.77.10/24`，平板为 `192.168.77.2/24`。
日常 USB 网络配置现已保存为 `pad2pro-usb`；RAM 文件服务已在维护结束后停止。
普通系统 SSH 不需要文件服务，只有再次临时启动 RAM 时才需要按下面步骤开启。
再次准备维护环境前，先检查是否已有该连接和运行中的文件服务，已有时无需重复创建。
从未配置的电脑可按下面示例创建临时网络配置；
这里的接口名是本机此前实测的名字，换 USB 端口后应重新核对：

```sh
nmcli connection add type ethernet \
  con-name pad2pro-usb ifname enp103s0f3u1u1 \
  ipv4.method manual ipv4.addresses 192.168.77.10/24 \
  ipv4.never-default yes ipv6.method disabled connection.autoconnect yes
python3 -m http.server 8000 --bind 0.0.0.0 --directory .work/ram-http-root
```

文件服务器使用专门的安装材料目录。监听所有本机地址，是为了在 USB 网卡尚未出现时
也能先启动服务器；不要把目录换成包含私钥的 `.work/` 根目录。

在电脑另一终端检查准备状态：

```sh
nmcli -g connection.id,connection.interface-name,ipv4.method,ipv4.addresses \
  connection show pad2pro-usb
ss -ltn 'sport = :8000'
readlink -e artifacts/nixos-pad2pro-ram-system-v2/rootfs.squashfs
ls -l .work/ram-http-root/rootfs-*.squashfs
```

应看到正确 USB 接口、`manual`、`192.168.77.10/24`，8000 端口处于 LISTEN，
配套文件存在。平板进入 Linux 后 USB 网卡才会出现；届时还需确认
`ip -4 address show enp103s0f3u1u1` 中实际分配了该地址。
如果同名网络配置已经存在，不重复添加；核对后在接口存在时执行
`nmcli connection up pad2pro-usb`。

让平板手动进入 fastboot，在电脑另一终端执行：

```sh
fastboot devices
fastboot boot artifacts/nixos-pad2pro-ram-system-v2/packed/boot.img
```

本机此前序列号为 `ca38d228`。选择 `Linux RAM fallback`，等待
root 终端提示符；完整 RAM 系统下载校验成功后会自动登录。
精简只读诊断镜像不能替代这个可运行安装工具的维护系统。
若下载超时进入紧急模式，先恢复 USB 连接、电脑的 IPv4 地址和文件服务。
先检查这些准备状态，不能用格式化 Android 解决下载问题。若本轮下载服务已经失败，
恢复电脑端准备后需要重新临时启动维护镜像；不能仅等着紧急模式自行进入登录界面。
电脑已经正确准备时仍失败，再结合屏幕最后几行和 USB 日志诊断。

核对启动镜像和物理 USB 设备后，直接连接：

```sh
ssh root@192.168.77.2
```

不需要 `-i` 或输入登录密码。首次连接仍会要求确认 SSH 主机指纹，核对设备后输入
`yes`；这个提示与用户登录密码不同。重启 RAM 后若提示主机密钥变化，先确认当前
确实是本机 RAM 环境，再使用 `ssh-keygen -R 192.168.77.2` 清除该地址的旧记录。
免密码 root 仅监听 USB 地址 `192.168.77.2`，不会改变已安装普通系统的登录策略。

## 3. 核对磁盘，再划出 Linux 空间

以下块设备命令在**平板 RAM 系统的 root shell** 中执行。电脑的 `/dev/sda`
可能是电脑自己的磁盘，不能在电脑 shell 中照抄这些命令。

先只读查看：

```sh
cat /proc/cmdline
lsblk -o NAME,SIZE,TYPE,FSTYPE,PARTLABEL,MOUNTPOINTS
blockdev --getss /dev/sda
blockdev --getsize64 /dev/sda
sfdisk --dump /dev/sda
```

本机实测为 4096 字节逻辑扇区，磁盘 508710354944 字节。先把主/备 GPT、
原厂恢复镜像、原 boot_a 和个人资料保存到电脑；RAM 中的备份重启就会消失。
GPT 和 boot 备份不包含 Android 照片、应用数据或旧 Linux 文件。

空间计算使用 GiB：1 GiB = 1073741824 字节。本机调整完成后的边界如下，
LBA 单位为 4096 字节，末尾包含在分区内：

| GPT 编号 | 标签 | 起始 LBA | 末尾 LBA | 扇区数 |
| --- | --- | ---: | ---: | ---: |
| 15 | `userdata` | 3617586 | 71505663 | 67888078 |
| 16 | `KShinC_BOOT` | 71505664 | 71767807 | 262144 |
| 17 | `NixOS_Root` | 71767808 | 124196607 | 52428800 |

修改 GPT 时，保留原分区 1～14、磁盘 GUID、分区 GUID、类型、属性及表长，
只调整上述目标分区的边界和标签。不能对 Android 加密 userdata 直接做普通文件系统缩容；
本机采用备份后重建 Android 数据区的方式。

实际工具流程是导出完整表、编辑并复核，然后写入完整的审定表：

```sh
sfdisk --dump /dev/sda > /run/current-layout.sfdisk
# 复制为 reviewed-layout.sfdisk，保留所有原有字段，仅编辑核准的目标项。
# 比较完整前后表；确保目标分区未挂载、没有 swap 或 holder。
# 先在电脑的普通文件副本演练，验证主/备 GPT 及保留条目。
sfdisk --lock=yes --sector-size 4096 --wipe never --wipe-partitions never \
  /dev/sda < /run/reviewed-layout.sfdisk
blockdev --rereadpt /dev/sda
udevadm settle
sfdisk --verify /dev/sda
```

`reviewed-layout.sfdisk` 必须是经核对的完整输入，不是仅含上述三行的表格。
本机 GPT 只有 32 项；不要让工具擅自扩成 128 项、覆盖前 34 个扇区。
历史执行守卫及布局见本机私有 `.work/apply-approved-layout.sh`；该脚本锁定了
安装前 GPT 摘要，当前设备状态已经不同，不应重新运行它。
`tools/plan-layout.py` 只读计算已有“userdata + 两个末尾 Linux 分区”的布局；
纯 Android、没有这两个分区的设备必须另外审定完整 GPT，不能直接套用。

## 4. 首次格式化和挂载 Linux 分区

这一节会清空两个 Linux 分区。现有安装的维护、改密码和日常升级都跳过格式化。
先核对两个 PARTLABEL 唯一，容量分别为 1 GiB、200 GiB，而且未挂载，再执行：

```sh
boot_part=/dev/disk/by-partlabel/KShinC_BOOT
root_part=/dev/disk/by-partlabel/NixOS_Root
mkfs.ext4 -b 4096 -I 256 \
  -O none,has_journal,ext_attr,resize_inode,dir_index,filetype,extent,64bit,flex_bg,sparse_super,large_file,huge_file,dir_nlink,extra_isize,metadata_csum \
  -E lazy_itable_init=0,lazy_journal_init=0 -L KShinC_BOOT "$boot_part"
mkfs.btrfs -L NixOS_Root "$root_part"
mkdir -p /mnt
chmod 755 /mnt
mount -o subvolid=5 "$root_part" /mnt
for name in root nix home log; do
  btrfs subvolume create "/mnt/@nixos-$name"
done
umount /mnt
mount -o subvol=@nixos-root,compress=zstd:1,noatime "$root_part" /mnt
mkdir -p /mnt/nix /mnt/home /mnt/var/log /mnt/boot
mount -o subvol=@nixos-nix,compress=zstd:1,noatime "$root_part" /mnt/nix
mount -o subvol=@nixos-home,compress=zstd:1,noatime "$root_part" /mnt/home
mount -o subvol=@nixos-log,compress=zstd:1,noatime "$root_part" /mnt/var/log
mount -o rw,noatime "$boot_part" /mnt/boot
findmnt -R /mnt
```

四个 Btrfs 子卷共同使用这 200 GiB，不需要给 `/home` 再切固定容量分区。
`/boot` 使用明确的 ext4 特性，是为了让 kShimC 的只读加载器能够读取。
NixOS 中默认以 `rw,noatime` 挂载，写入受 root 所有权及普通文件权限限制。
加载器只读访问文件系统，不要求 Linux 运行时将它挂载为只读。
现有旧签名可能使 mkfs 拒绝；遇到拒绝应重新核对目标，不直接追加强制参数。

## 5. 把 NixOS 安装进根分区

在电脑查看已经信任的安装缓存公钥：

```sh
cat artifacts/nixos-pad2pro-install-v7/cache-key.pub
```

在平板 RAM 系统导入签名缓存，`trusted_key` 必须填入上面核对的完整公钥；
这是公开的缓存校验密钥，只校验下载包，不用于登录；不需要创建个人登录密钥。
不要使用 `.work/cache-keys/install.sec` 私钥：

```sh
trusted_key='填入已核对的 cache-key.pub 完整内容'
system=$(curl --fail --silent --show-error \
  http://192.168.77.10:8000/install-v7/system-path)
nix --extra-experimental-features 'nix-command flakes' copy \
  --from http://192.168.77.10:8000/install-v7/cache \
  --option extra-trusted-public-keys "$trusted_key" "$system"
```

这一步导入 RAM 系统的 Nix store；随后 `nixos-install` 会把完整系统闭包复制到
`/mnt`。不能仅复制内核或一个 boot.img 就认为已经安装根系统。

在电脑另一终端，把与该系统配套的配置传入 `/mnt/etc/nixos`：

```sh
tar -C artifacts/nixos-pad2pro-install-v7/config -cf - . | \
  ssh root@192.168.77.2 \
    'mkdir -p /mnt/etc/nixos && tar --no-same-owner -xf - -C /mnt/etc/nixos'
```

在平板 RAM 系统执行安装：

```sh
nixos-install --no-channel-copy --no-root-password --system "$system" --root /mnt
nix-store --store /mnt --verify --check-contents
cat /mnt/boot/kshim/systems/nixos/entries.conf
ls -l /mnt/nix/var/nix/gcroots/kshim-nixos
```

外部启动器钩子会把本代 Image、DTB、initramfs 发布到 ext4 `/boot`，并保留 GC roots。
`--no-root-password` 保持当前约定：root 和普通账户均不设置密码。
确认安装、挂载和启动条目正确后，先卸载再重启：

```sh
sync
umount /mnt/boot /mnt/var/log /mnt/home /mnt/nix /mnt
```

## 6. 重建 Android 数据区，测试和固化菜单

首次改变 userdata 大小后，按已审定流程重建 Android 数据区。本机最终还需要用户
在原厂 recovery 中选择清除数据，才恢复 Android 启动。此操作会清除 Android 数据；
正常使用后的启动故障不应直接照此重新清除，也不应重复历史 fastboot erase 脚本。

先临时测试保留 Android 的菜单，电脑执行：

```sh
fastboot boot artifacts/nixos-pad2pro-menu-pagination-v3/boot.img
```

分别测试一级菜单 Android、Linux → NixOS → 当前代。两条路径都正确、原 boot_a
备份已保存、当前槽位和镜像均核对后，才写入对应槽位。本机验证时是 a 槽：

```sh
fastboot getvar current-slot
# 仅在结果确认为 a、镜像匹配本机且临时测试通过后执行：
fastboot flash boot_a artifacts/nixos-pad2pro-menu-pagination-v3/boot.img
```

另一台设备/另一槽位不能照抄 `boot_a`。本次实际固化是在 RAM 维护环境完成写入、
同步并完整读回校验，效果同为更新已核准的 boot_a；boot_b 保持原样。
完成后验证不依赖 fastboot boot 的 Android → NixOS → Android 往返、前一代回退。

## 7. 这台已经安装好的平板，现在怎样使用

直接重启，在 kShimC 中选择 Linux → NixOS → 当前代（`7d548890…`，内核标识 `wifi1`）。
前一代 `9bb09c19…` 额外带固定只读诊断接口，普通使用选当前代。

项目不预置普通用户名。登录时使用自己创建的账户，例如将下面的 `USERNAME` 替换为自己的用户名。
以下首次设置步骤用于新装系统：在完整 RAM
维护环境中**只挂载现有子卷**，不要执行上面的 GPT/mkfs 操作。参照
`.work/mount-existing-nixos.sh` 的挂载步骤，挂载到 `/mnt` 后，由你交互设置：

```sh
nixos-enter --root /mnt -c 'useradd --create-home --groups wheel,networkmanager -- USERNAME'
nixos-enter --root /mnt -c 'passwd -- USERNAME'
```

若账户已经存在，只执行密码命令。`wheel` 是管理员角色，普通账户创建时不添加该组。
随后同步、卸载，重启进入当前代，使用自己的账户登录，管理员可用 `sudo` 管理。
SSH 命令为 `ssh USERNAME@192.168.77.2`。密码由用户在自己的终端交互输入，
不进入构建输入或聊天记录。系统默认 Shell、桌面和用户服务对所有账户提供，
无需为每个用户名另写声明配置。

以后编辑 `/etc/nixos` 并更新系统：

```sh
sudo nixos-rebuild boot --flake path:/etc/nixos#pad2pro
```

日常更新不重新分区，也不重新写 Android boot_a；kShimC 启动项安装器更新共享 Linux `/boot`。
平板维护配置复用已验证内核；新内核由电脑显式构建，详细流程见
[适配状态](STATUS.md) 与 [更新回退](UPDATES.md)。
