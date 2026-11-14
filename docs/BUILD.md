# 在其他 Linux 电脑上构建

适用于 x86_64 和 ARM64 Linux。电脑不必运行 NixOS。先一次性安装 Nix、Git，
x86_64 额外配置 ARM64 用户态仿真；随后普通克隆、进入项目、执行 `nix build` 即可。
固件、补丁快照和音频源码都在仓库中，不需要从原作者电脑复制文件。

## 为什么构建会用到 QEMU

`pad2pro-build` 只对内核使用 x86_64 → ARM64 交叉编译；系统用户空间仍按
`aarch64-linux` 原生方式构建。构建过程会执行 ARM64 的 shell、编译器及辅助程序，
所以 x86_64 主机需要用 QEMU 用户态仿真运行它们。这与调试平板是不同用途。
二进制缓存可避免很多编译，但定制包和缓存未命中的构建仍需 ARM64 执行能力。

| 构建电脑 | 配置 | 执行方式 |
| --- | --- | --- |
| x86_64 Linux | `pad2pro-build` | 内核交叉编译，ARM64 用户空间通过 QEMU/binfmt 执行 |
| ARM64 Linux | `pad2pro` | 全部原生执行，无需 QEMU |

已有真正 ARM64 远程 builder 的 x86_64 电脑，也可以将 ARM64 构建交给它。
本指南采用本机用户态仿真，不需要另一台电脑或完整 ARM 虚拟机。

## 一次性准备：所有电脑

安装 Git、curl、CA 证书和 Nix 2.31 或更新版本。GCC、Python、m4、ALSA 工具、
设备树编译器等由 Nix 自动提供，不需要在宿主发行版逐个安装。
支持 systemd 的发行版可按 [Nix 官方安装说明](https://nix.dev/install-nix/installing-nix.html)
安装多用户 Nix；已有 Nix 的电脑直接复用。安装后重新打开终端，确认：

```sh
nix --version
git --version
uname -m
```

在 `/etc/nix/nix.conf` 合并以下设置，不覆盖已有配置：

```ini
experimental-features = nix-command flakes
```

多用户安装修改配置后，使用管理员权限执行：

```sh
sudo systemctl restart nix-daemon.service
```

单用户安装将相同设置放入 `~/.config/nix/nix.conf`，不需要重启 daemon。
ARM64 电脑可直接跳到“克隆后构建”。

## 一次性准备：x86_64 的 ARM64 仿真

需要 QEMU 的 AArch64 用户态模拟器及 binfmt 注册配置。常见发行版的软件包如下；
管理员可使用 `sudo`，或按当地系统配置换成 `run0`／root 执行。

| 发行版 | 安装命令 |
| --- | --- |
| Debian 13+、Ubuntu 25.10+ | `sudo apt install qemu-user qemu-user-binfmt` |
| Debian 12、Ubuntu 22.04／24.04 | `sudo apt install qemu-user-static binfmt-support` |
| Arch Linux／CachyOS | `sudo pacman -S qemu-user-static qemu-user-static-binfmt` |
| Fedora | `sudo dnf install qemu-user-static-aarch64 qemu-user-binfmt` |
| NixOS | 在主机配置中声明 `boot.binfmt.emulatedSystems = [ "aarch64-linux" ];`，然后激活主机配置 |

其他发行版安装同等功能的软件包。现代 Debian／Ubuntu 已将旧的
`qemu-user-static` 合并或改为兼容包，包名应以所用发行版的版本为准。
安装后，在使用 systemd 的非 NixOS 主机执行：

```sh
sudo systemctl restart systemd-binfmt.service
cat /proc/sys/fs/binfmt_misc/*aarch64*
```

应看到 AArch64 项为 `enabled`、`interpreter` 指向 QEMU，且 `flags` 包含 `F`。
`F` 让内核保持模拟器可用，适合 Nix 构建隔离；建议使用发行版提供的静态模拟器。
旧 Debian／Ubuntu 若由 binfmt-support 管理，可执行
`sudo update-binfmts --enable qemu-aarch64` 后再检查。

在非 NixOS 的 x86_64 主机，将以下设置合并到 Nix 配置：

```ini
extra-platforms = aarch64-linux
```

多用户 Nix 将它写入 `/etc/nix/nix.conf` 并重启 `nix-daemon.service`；
单用户 Nix 写入用户配置即可。该设置告诉 Nix 主机具备 ARM64 执行能力，
它本身不会安装或注册 QEMU。

保留 Nix 的正常 sandbox 与签名校验设置。如果隔离构建提示找不到模拟器，
将上面 `interpreter` 的实际路径加入 `extra-sandbox-paths`，例如 Arch：

```ini
extra-sandbox-paths = /usr/bin/qemu-aarch64-static
```

其他发行版按实际路径填写。若它是符号链接，同时暴露 `readlink -f` 得到的目标路径；
某些发行版的入口位于 `/usr/libexec/qemu-binfmt/`。修改后重启 Nix daemon。
没有 `enabled`／`F` 的注册项、宿主缺少 binfmt_misc 支持时，应先修复注册，
不要仅增加 `extra-platforms` 或关闭 sandbox。

## 克隆后构建

在同一工作目录使用公开仓库地址克隆：

```sh
git clone https://github.com/ZEGEIZI/NixOS_for_OnePlus-Pad2Pro.git
git clone https://github.com/ZEGEIZI/linux-sm8750-erhai-patchset.git
git clone https://github.com/ZEGEIZI/kShimC-oneplus-pad2-pro.git
```

克隆后的目录：

```text
workspace/
  NixOS_for_OnePlus-Pad2Pro/
  linux-sm8750-erhai-patchset/
  kShimC-oneplus-pad2-pro/
```

普通 NixOS 构建使用本仓库已校验的依赖快照，不需要手动同步另外两个目录。
补丁集仓库用于维护设备支持，kShimC 仓库也用于构建菜单本体。
在 NixOS 项目中先做轻量验证：

```sh
cd NixOS_for_OnePlus-Pad2Pro
nix flake check --all-systems --no-build
nix build .#firmware .#bluetooth-firmware
```

x86_64 电脑先验证真正的 ARM64 构建进程能运行，再构建完整系统：

```sh
nix build .#checks.x86_64-linux.arm64-execution -L
nix build .#nixosConfigurations.pad2pro-build.config.system.build.toplevel -L
```

ARM64 电脑直接构建：

```sh
nix build .#nixosConfigurations.pad2pro.config.system.build.toplevel -L
```

`result` 指向构建结果。x86_64 上第一次运行 ARM64 检查会从 Nix 缓存获取
小型 ARM64 构建工具并执行；若出现 `Exec format error`，检查 binfmt 注册。
若 Nix 报不支持 `aarch64-linux`，检查 daemon 实际读取的 `extra-platforms`。
检查完成后可删除 `result` 链接，不影响 Nix store。

## 构建与安装的边界

普通构建不需要连接平板、ADB、fastboot、工厂分区、个人账户或 `local.nix`。
安装和发布启动项时，才按 [安装说明](INSTALL.md) 核对目标平板自己的分区及 PARTUUID。
每台平板的蓝牙地址在运行时独立读取，不能复用另一台设备的身份或分区配置。

仅构建 NixOS 系统无需安装 Podman 或 Android 平台工具；构建 kShimC 菜单本体
使用独立 kShimC 仓库的构建环境，按它的 README 准备。

参考：[NixOS ARM 构建](https://wiki.nixos.org/wiki/NixOS_on_ARM/Building_Images)、
[Debian QEMU 用户态仿真](https://wiki.debian.org/QemuUserEmulation)、
[Arch QEMU](https://wiki.archlinux.org/title/QEMU)、
[Fedora AArch64 静态模拟器](https://packages.fedoraproject.org/pkgs/qemu/qemu-user-static-aarch64/)。
