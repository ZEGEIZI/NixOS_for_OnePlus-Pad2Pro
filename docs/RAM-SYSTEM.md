# 完整 RAM 维护系统

`modules/ram-system.nix` 从同一份基础配置生成内存系统。根目录为 tmpfs，Nix store
使用 squashfs + tmpfs overlay；配套系统文件从电脑经 USB 下载，并用启动命令行
中的 SHA-256 校验。它关闭 GPT 自动挂载，不自动挂载或格式化平板的物理文件系统。

## 免密码 USB 登录与本地自动登录

按用户选择，日常教程使用免密码模式。它只作用于临时 RAM 维护系统：

- 平板下载并校验系统后，tty1 自动登录 root。
- 电脑执行 `ssh root@192.168.77.2`，不需要用户密钥或登录密码。
- SSH 只监听 USB 地址 `192.168.77.2`，防火墙仅在 usb0 开放端口 22。
- RAM 的免密码设置不改变普通 NixOS 的认证策略；本机普通 `nixos` 用户已另行设置密码。

构建：

```sh
python3 tools/build-ram-system.py --passwordless --out-link result-ram-system
python3 tools/pack-probe.py --profile system --payload result-ram-system \
  --kshim-project /path/to/kShimC-oneplus-pad2-pro \
  --boot-tools /path/to/verified-ext4-boot-tools \
  --stock-boot /path/to/original-boot.img --output ./ram-system-v2
```

本机已经准备好 `artifacts/nixos-pad2pro-ram-system-v2/packed/boot.img` 和对应
`rootfs.squashfs`。v2 已实机启动验证：USB 免密码 SSH、本地 root 自动登录和文件校验通过，
实时报告 0 个失败服务。普通安装系统使用用户另行设置的 `nixos` 密码，root 保持锁定。

## 电脑准备与启动

先准备 USB 网卡 `192.168.77.10/24`，并持续运行配套文件服务器，再执行
`fastboot boot`。新构建的 payload 目录自带 `rootfs-<SHA-256>.squashfs` 文件名链接，
供镜像获取准确配套的系统文件。直接提供整个 payload 目录即可：

```sh
python3 -m http.server 8000 --bind 0.0.0.0 --directory result-ram-system
```

本机教程的 `.work/ram-http-root/` 已包含 v2 的对应链接，也保留 v1 所需的旧文件；
不用用新版文件覆盖 v1 的 `rootfs.squashfs`。
首次连接需要确认 SSH 主机指纹；RAM 重启会重新生成主机密钥，出现变化提示时先
核对实际设备及镜像，再清除该地址的旧记录，不关闭全局 SSH 主机验证。

单独执行 `fastboot boot` 而没有电脑 IPv4 地址及 HTTP 服务，会停在下载阶段。
下载服务已失败进入紧急模式时，恢复电脑准备后重新临时启动。完整配置及检查步骤
见 [操作教程](TUTORIAL.md)。完成整个维护过程后，再停止文件服务器并清理临时网络。

## 可选的密钥模式

若需要密钥认证，使用现有公钥构建，不传 `--passwordless`：

```sh
python3 tools/build-ram-system.py --authorized-key /path/to/id_ed25519.pub
```

该模式保持 root 密码锁定、仅允许指定公钥登录。私钥留在电脑，不放入构建输入。
两种登录模式由构建时显式选择，不能同时传入。

## 验证范围

完整 RAM v1 的 NixOS、认证 SSH、SCMI、zram 和普通文件镜像的 Btrfs/ext4 测试已通过。
v1 缺少 `xt_pkttype` 导致的防火墙错误已在新内核配置中修复，v2 使用已在正式系统
启动验证的这套内核。v2 的离线检查包含构建、镜像打包、配置隔离及配套 HTTP 文件。
v1 曾临时启用免密码 USB SSH 与 tty1 自动登录；随后 v2 从新镜像启动，
两项功能和正常防火墙均已实测。旧 v1 内核的防火墙问题与新版本分开记录。

RAM 启动和维护不自动改动分区或设置已安装系统的密码。硬件限制见
[适配状态](STATUS.md)；没有失败服务也不代表全部硬件已验收。
