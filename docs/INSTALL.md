# 安装与验证

按操作顺序学习请先读 [从分区到安装的教程](TUTORIAL.md)。

完整 NixOS 已在平板内存中启动，并经 USB SSH 读取实际服务和硬件状态。
本机已在用户确认备份及数据清除后完成重分区和 Btrfs 安装。
用户已确认 Android 初始化向导/系统和 NixOS 存储启动；v6 测试代 USB 与子卷已实测。
普通当前代已验证 USB NCM、SSH 主机身份及默认关闭的 HTTP 诊断；
菜单手选前一代回退及 Android → NixOS → Android 的持久菜单往返均已通过。

## 目标布局

使用 GPT PARTLABEL（区分大小写和拼写）：

| 用途 | PARTLABEL | 文件系统 | 容量 |
| --- | --- | --- | --- |
| 共享 Linux 启动文件 | `KShinC_BOOT` | ext4 | 1 GiB |
| NixOS | `NixOS_Root` | Btrfs | 200 GiB |

`KShinC_BOOT` 是用户指定的拼写。它不是 Android `boot_a` / `boot_b`。
本机原有的 `ARMADA_BOOT` / `ARMADA_ROOT` 已按授权重建为上述布局。
本节容量是本机执行结果；其他设备必须重新核对 GPT。
`tools/plan-layout.py` 校验 GPT 校验和并输出布局建议，完全不写设备。
设备本次采集结果保存于被 Git 忽略的 `.work/`。

200 GiB 根分区意味着将此设备的 userdata 从约 331.97 GiB 改为
258.97 GiB。需要备份并重建 Android userdata，以及清除旧 Linux 数据。
只有在核对当前 GPT、异机备份、原厂恢复文件和具体方案后，才执行分区操作。
不对 Android 的加密 userdata 做未经验证的原位缩小。

本机重分区后，Android 最终通过原厂 recovery 的清除数据操作完成数据区重建，
随后正常启动。fastboot erase 的 OKAY 不等同于完成格式化和 Android 加密初始化。
此步骤属于首次安装的数据清除流程；已正常使用后的启动故障应先诊断，
不能据此反复擦除 userdata/metadata。

## 蓝牙首次初始化

蓝牙服务会从每台设备自己的 `nonmodemst1` / `nonmodemst2` 工厂分区提取原厂
地址，校验后自动配置。首次安装不需要进入 Android 导出地址，也不需要预置
`/var/lib/oneplus-pad2pro/bt-address`。保留上述工厂分区，不要把本机地址缓存
复制进另一台设备的安装镜像。当前已通过删除缓存后的真实重启验证；不同 ROM
或第二台设备的实际验收仍需核对。详情见 [蓝牙适配](BLUETOOTH.md)。

## 构建

当前默认包含已验收的 5 GHz Wi-Fi 修复，驱动内建。通用固件归档随仓库提供，
克隆后可直接构建，无需另行准备或导入；见 [固件说明](FIRMWARE.md)。
后续内核构建检查内建配置，不允许悄悄降为模块。

电脑需先按 [跨发行版构建环境](BUILD.md) 安装 Nix，并在 x86_64 上准备 QEMU/binfmt。
ARM64 Linux 可原生构建。环境准备完成后：

```sh
nix flake check --no-build
nix build .#checks.x86_64-linux.boot-publication
nix build .#packages.x86_64-linux.kernel -L
```

在 x86_64 电脑上构建首次部署：

```sh
nix build .#nixosConfigurations.pad2pro-build.config.system.build.toplevel -L
```

这个配置只对内核使用 Nix 管理的交叉编译，其余为原生 ARM64 用户空间，
优先使用官方二进制缓存；电脑需要 ARM64 binfmt/QEMU 或真正的 ARM64 builder，
并让 Nix 接受 `aarch64-linux` 构建。不要关闭签名校验。

平板本机维护使用 `nixosConfigurations.pad2pro`，电脑使用 `pad2pro-build`。
两者均从当前 nixpkgs 的官方 `linux_7_3` 内核包构建，应用随项目保存的固定补丁集。
内核、模块、DTB 和 initrd 统一引用最终系统内核；更新 nixpkgs 可更新同系列正式版和工具链。
不使用历史闭包断言，不回退到较旧内核系列。候选验收和来源见
[补丁集迁移](KERNEL-PATCHSET.md)；旧实机记录保留在 [历史源码记录](history/KERNEL-SOURCE.md)。

## 离线启动文件导出

```sh
nix run .#kshim-install -- --staging-root ./boot-export ./result
```

导出包含 `kshim/systems/nixos/` 及默认返回 Android 的初始 `boot.conf`。
这一步不安装根系统，也不写设备。导出目录的 `.nixos-gcroots/` 只是离线记录，
不能代替目标系统上的实际 GC root。

载荷限制：单文件至多 128 MiB，DTB 至多 1 MiB，包含 Image 运行时大小的总量
至多 256 MiB。kShimC 启动项安装器会检查摘要、ARM64 Image 头和设备树兼容标识。

## kShimC 对接

独立项目 `kShimC-oneplus-pad2-pro` 是菜单实现来源。当前已构建的菜单若仍固定
旧 boot PARTUUID，**只更改分区标签并不能让它找到新分区**。
重建时使用 `inputs/kshim-partition.config` 中的选择：清空旧 PARTUUID，按唯一
`KShinC_BOOT` 查找。也可以使用新分区的真实 PARTUUID，并同时更新本机 NixOS 配置。
完整菜单配置必须保留项目原有的设备、UFS、显示及按键配置，不能只用这两行替代。

可使用本仓库的封装，从独立项目的固定提交导出干净源码，应用菜单显示补丁并替换
两项分区查找设置，然后调用其原有构建入口。`(current)` / `(previous)` 位于内核
名称和详情的最前面，长版本名在右侧截断时仍能看到状态；补丁摘要记录在 `source.json`：

```sh
python3 tools/build-menu.py --kshim-project /path/to/kShimC-oneplus-pad2-pro \
  --stock-boot /path/to/original-boot.img --output ./menu-build-v1
```

需要独立项目记录的固定 Docker 工具链镜像及其构建依赖；脚本不安装工具、不访问设备。
输入必须是原始 boot 镜像，不能使用已注入 kShimC 的 boot 分区备份再次打包。

首次测试使用匹配原厂 boot 的 kShimC `fastboot boot` 镜像，保留 Android 路径。
实机启动、刷写和重分区由用户明确安排；本仓库的构建命令均不自动执行这些操作。

ext4 需使用加载器支持的特性；建议从显式最小特性集创建，避免发行版默认新增
`orphan_file` 等不支持的特性。实施时在普通文件镜像上先验证参数，再用于已确认分区：

```sh
mkfs.ext4 -b 4096 -I 256 -O none,has_journal,ext_attr,resize_inode,dir_index,filetype,extent,64bit,flex_bg,sparse_super,large_file,huge_file,dir_nlink,extra_isize,metadata_csum \
  -E lazy_itable_init=0,lazy_journal_init=0 boot-filesystem.img
```

需要创建镜像文件并核对大小后才能执行示例。不得把示例路径直接替换成未核查的块设备。
发布完成后同步，离线镜像检查前干净卸载文件系统，再使用独立 kShimC 的主机
检查器验证整个 ext4 镜像；加载器不会回放 journal。NixOS 运行时的 `/boot`
默认以 `ro,noatime` 挂载。安装器和清理器仅在操作期间临时改为可写，
同步后恢复只读；即使接管旧配置的可写挂载，操作结束也会改为只读。
长期可写的 ext4 即使没有文件写入，也会设置 `needs_recovery`；强制重启后
kShimC 会拒绝读取整个启动分区。文件权限不能避免这一问题。

## Btrfs 和系统安装

根分区建立 `@nixos-root`、`@nixos-nix`、`@nixos-home`、`@nixos-log` 四个子卷，
分别挂载 `/`、`/nix`、`/home`、`/var/log`。`/nix` 必须在 initrd 中挂载。
先在维护环境挂载目标系统到 `/mnt`，检查所有挂载点对应的实际分区，
再按 NixOS 标准的
`nixos-install --no-root-password --system <已构建系统闭包> --root /mnt` 安装。
`--no-root-password` 遵守用户暂不设置密码的要求，账户保持初始锁定。
安装目录及其父目录须允许访问（标准 `/mnt` 使用 0755）；从电脑的归档提取配置时，
使用 `tar --no-same-owner`，确保 `/etc/nixos` 中的文件归 root 所有。
离线构建电脑必须先通过 `nix copy --to <目标 store>` 复制闭包；只复制 `/boot`
不足以安装 NixOS。维护环境须提供 Nix、Btrfs 和 ext4 工具。

可在电脑导出带签名的离线安装缓存。签名私钥保留在电脑的忽略目录中，不作为
Nix 构建输入，也不放入导出的安装材料：

```sh
mkdir -p -m 700 .work/cache-keys
nix key generate-secret --key-name pad2pro-install > .work/cache-keys/install.sec
chmod 600 .work/cache-keys/install.sec
bash tools/export-installation.sh ./install-bundle .work/cache-keys/install.sec
```

缓存包含基础系统闭包，`linux-boot.ext4` 是共享 Linux 启动分区的 ext4 文件系统镜像，
`config/` 包含完整的声明式配置，`cache-key.pub` 用于校验安装缓存。传输并核对安装材料后，在维护
环境显式信任该公钥导入闭包；不要关闭签名校验。已有签名私钥时直接复用，不重新生成。

导出器先创建干净的 `config/` 快照，再从该快照构建，确保导出的配置就是构建输入。
默认不带入仓库中被忽略的 `hosts/pad2pro/local.nix`。如需生成本机安装材料，
通过第三个参数显式传入本机模块：

```sh
bash tools/export-installation.sh ./device-install-bundle .work/cache-keys/install.sec \
  .work/pad2pro-install-local.nix
```

本机模块只包含 GPT PARTUUID、USB 网络开关等声明式设置，不能包含密码或私钥。
导出器会将它放入 `config/hosts/pad2pro/local.nix`，并以 `path:` flake 构建，
使该文件即便被 `.gitignore` 排除也会生效。导出操作不修改设备。

在 `hosts/pad2pro/local.nix` 填写本机值，例如：

```nix
{
  boot.loader.kshim.bootPartuuid = "实际 GPT PARTUUID";
  hardware.oneplus-pad2pro.usbNetwork.enable = true;
}
```

Git flake 默认不包含忽略文件；使用本机配置时需显式纳入本地 flake 源（例如
`nixos-rebuild --flake path:/etc/nixos#pad2pro`），或在自己的私有配置仓库中导入模块。
密码和 SSH 私钥不得写入 Nix 文件。

`path:` 输入会收集目录内容，不遵循 Git 的忽略规则。不要对包含 `.work/`、
`artifacts/`、私钥或磁盘镜像的开发目录直接使用 `path:`；上面的导出器会先创建
只含指定源码目录的 `config/` 快照，再导入该快照。Git 工作目录中的常规构建使用
`nix build .#…`，新增源码需先纳入 Git 索引。

项目不创建默认普通账户，不在 Nix 配置中绑定个人用户名、UID 或家目录。
每个人通过 GNOME 用户管理或标准账户工具选择自己的用户名和账户类型。
Fish、GNOME 默认设置、字体、输入法及音频服务都通过系统级配置对所有用户提供。

首次安装可在维护环境挂载目标系统后执行以下命令，将 `USERNAME` 替换为自己选择的用户名：

```sh
nixos-enter --root /mnt -c 'useradd --create-home --groups wheel,networkmanager -- USERNAME'
nixos-enter --root /mnt -c 'passwd -- USERNAME'
```

此示例创建管理员；普通账户不添加 `wheel` 组。密码在终端交互设置，不写入构建输入。
维护环境中的交互密码辅助工具为 `tools/set-user-password.sh USERNAME`，它要求明确指定账户。
`users.mutableUsers = true` 保留自己创建的账户和密码，后续系统更新不要求把账户写进 Nix 文件。
共享默认值集中在 `modules/user-defaults.nix`。该模块还在系统激活前后保留非声明式账户的
附属 UID/GID 范围，避免标准激活重写 `/etc/subuid`、`/etc/subgid` 时丢失手工账户映射。
注意：移除曾经受 Nix 管理的账户声明会删除原账户，即使 `mutableUsers = true`；
已有账户转为手工管理时必须先备份账户数据库并安全迁移，不能仅删除声明。

## 验收

实机必须逐项记录：NixOS initrd、Btrfs 子卷、文本控制台、USB 键盘、USB NCM、
Wi-Fi、充电、电量、温控、关机、重启、Android 返回、两个不同代际的手选回退。
上述为基础系统验收范围；GNOME 桌面配置和验收见 [GNOME 桌面](GNOME.md)。
扬声器配置和自动失败回退仍未完成。

USB NCM 启用后平板为 `192.168.77.2/24`，电脑可手动配置同网段地址；服务只提供
正常认证的 SSH。`hardware.oneplus-pad2pro.usbNetwork.inInitrd` 默认开启：在 initrd
绑定 gadget，跨 switch-root 保留，由正常系统的 networkd 管理地址；不提供 initrd
远程 shell，也不要求网络才能挂载 Btrfs 根系统。该路径复用已经实测的 RAM 初始化。

需要不解锁账户的只读调试时，可在本机模块显式开启：

```nix
hardware.oneplus-pad2pro.usbNetwork.diagnostics.enable = true;
```

该选项默认关闭。开启后仅绑定 USB 地址 `192.168.77.2:8080`，并仅在 `usb0`
开放防火墙端口。固定接口为 `/cgi-bin/status`、`/cgi-bin/dmesg` 和
`/cgi-bin/previous-boot`，不接收执行命令；不会改变账户或密码。
状态接口读取 PID 1 的挂载表，避免服务自身的只读沙箱影响挂载结果。
