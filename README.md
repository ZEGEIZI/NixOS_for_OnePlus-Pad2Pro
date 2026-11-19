# NixOS for OnePlus Pad 2 Pro

为 OnePlus Pad 2 Pro（OPD2413 / erhai / SM8750P）提供带 GNOME Wayland 桌面的 NixOS。
使用独立 kShimC 项目与 Android 共存；设备支持、内核、固件及启动发布由 Nix 声明。

设备集成只依赖 `linux-sm8750-erhai-patchset` 和 `kShimC-oneplus-pad2-pro` 的
版本化快照。音频源码、固件清单和桌面集成在本仓库维护，构建无需其他发行版仓库。
目录职责和依赖更新见 [维护指南](docs/DEVELOPMENT.md)。
另一台电脑的 Nix、QEMU/binfmt 软件安装及构建步骤见 [跨发行版构建](docs/BUILD.md)。

本项目的“kShimC 启动项安装器”（`nixos-kshim-install`）负责读取 NixOS Bootspec，
按独立 kShimC 项目的规范安装启动文件和配置，并维护对应的 Nix GC roots。
它由 NixOS 的外部引导器安装钩子调用；相同启动载荷在 `/boot` 内以硬链接共享，
每代保留独立启动描述。kShimC 本体只读加载准备好的启动项。

桌面及用户空间追踪 `nixos-unstable`，当前构建快照为 GNOME 51.0、Mesa 26.3.0 和
Firefox 160.0；该快照已通过原生内核及关键外设验收，详见下方补丁集文档。所有内核构建和模块聚合工具统一随 `nixpkgs` 更新，
不保留独立旧工具链，也不使用历史闭包路径断言限制更新。
中文字体、拼音和 200% 默认缩放已声明，安装和更新方式见 [GNOME 桌面](docs/GNOME.md)。
HDR 默认采用 10bit 等效精度，保留可手动选择的 12bit 等效输出和高精度原生
HDR 播放器。按内容调节全局背光和 SDR 白位补偿已通过实机会话及目视检查。显示精度、
背光校准状态及 HDR 的适配边界见
[显示精度与 HDR](docs/DISPLAY-COLOR.md)。
USB-C 支持 DisplayPort Alt Mode 外屏画面与声音，音频设置见 [USB-C 外屏音频](docs/AUDIO.md#usb-c-外屏音频)。
mpv 与 Chromium 的 Iris/V4L2 配置、补丁和验证方法见
[视频硬件解码](docs/VIDEO-DECODING.md)。

基础适配与实机安装已完成：NixOS 26.05 从 Btrfs 启动到文本登录，
USB NCM、SSH 主机身份、SCMI 调频、基础服务和 zram 已验证。
kShimC 已固化到 boot_a，Android → NixOS → Android 往返、菜单手选前一代回退、
实机 GC 后保留代际启动均通过。普通当前代默认关闭 HTTP 诊断。

目标分区：`KShinC_BOOT`（1 GiB ext4）与 `NixOS_Root`（200 GiB Btrfs）。
不预置普通用户名。每个人自行创建账户；Shell、桌面、输入法和音频默认设置对所有用户生效。
Fish 为全局默认 Shell，账户和密码可通过 GNOME 用户管理或标准账户工具管理；USB SSH 继续用于维护。

有线快充、GNOME 电池净功率显示和接电时熄屏保活已集成到 p6，
VCBAOBCH 的 SUPERVOOC、高电量接入、锁屏持续充电和充满保活已实测，详见 [充电说明](docs/CHARGING.md)。

p7 增加 NT36536 默认笔扫描，重启后书写、实际压感及恢复后扫描已验证；
首次需连接笔的蓝牙，详见 [手写笔输入](docs/PEN.md)。

Wi-Fi 修复已固化为默认构建基线：采用 OPD2413 专用固件
路径与整套原厂固件，cfg80211、mac80211、ath12k 明确内建。5 GHz 信道 40 的
扫描、关联和联网已实机验证，并由用户确认修复。
基础、Wi-Fi 和蓝牙固件随仓库提供，克隆后自动校验，无需额外导入；见 [固件说明](docs/FIRMWARE.md)。

```sh
nix flake check --no-build
nix build .#checks.x86_64-linux.firmware-inputs .#checks.x86_64-linux.wifi-firmware
nix build .#checks.x86_64-linux.boot-publication
nix build .#nixosConfigurations.pad2pro-build.config.system.build.toplevel -L
```

`pad2pro-build` 在电脑交叉编译内核、构建原生 ARM64 用户空间；需要 ARM64
binfmt/QEMU 或 ARM64 builder。`pad2pro` 在平板原生构建内核，供本机维护使用，
更新时不要求 x86 构建机。

内核使用 nixpkgs 的官方 `linux_7_3` 源码，构建时应用
`linux-sm8750-erhai-patchset`；补丁发布快照随本项目保存在
`inputs/kernel-patchset`，不依赖旧 fork 工作区或电脑上的绝对路径。
`pad2pro` 与 `pad2pro-build` 通过 `boot.kernelPatches` 使用同一补丁集和
`packages/nixos.config`，保留 sched_ext/BTF 支持。当前内核为 `7.3.4-erhai-p7`，
已完成完整系统构建和笔输入分项实机验收；
p6 已完成交叉内核与原生 ARM64 用户空间构建及充电实测；
旧 p5 的原生内核构建和关键外设验收作为历史记录保留，设备仍保留 p5 回退项。
维护与实机记录见 [补丁集迁移](docs/KERNEL-PATCHSET.md)，调度器见 [SCX 使用说明](docs/SCX.md)。
同系列随 nixpkgs 更新，跨系列前移适配；不降级、不增加旧系列兼容分支。
所有构建与模块聚合使用当前 nixpkgs 工具链。

RAM 诊断镜像单独构建 NixOS systemd initrd，不挂载设备文件系统：

```sh
nix build .#nixosConfigurations.pad2pro-probe.config.system.build.diagnosticPayload -L
```

该输出是匹配的 Image、DTB、initramfs 和命令行，还需通过独立 kShimC 打包，
才能作为 Android Boot Image 临时测试。不会自动启动或写入设备。

- [从分区到安装的操作教程](docs/TUTORIAL.md)
- [安装、分区与首次接入](docs/INSTALL.md)
- [本机分区方案与执行记录](docs/PARTITION-PLAN.md)
- [代际更新与回退](docs/UPDATES.md)
- [GNOME 桌面与滚动更新](docs/GNOME.md)
- [RAM 诊断启动](docs/DIAGNOSTIC.md)
- [完整 RAM NixOS 测试](docs/RAM-SYSTEM.md)
- [当前验证状态](docs/STATUS.md)
- [CPS8601 可选固件报错修复](docs/CPS8601.md)
- [Wi-Fi 固件差异与适配](docs/WIFI.md)
- [蓝牙原厂地址自动初始化与验证](docs/BLUETOOTH.md)
- [蓝牙支持的跨发行版安装](support/README.md)
- [来源及许可](NOTICE)
- [项目结构与维护](docs/DEVELOPMENT.md)
- [参考项目功能对照](docs/MAINLINE-COMPARISON.md)
- [跨发行版构建与仿真环境](docs/BUILD.md)
- [随仓库提供的固件](docs/FIRMWARE.md)
- [原始规划（历史）](docs/history/INITIAL-PLAN.md)

普通安装系统使用认证登录；RAM 维护镜像可显式启用 USB 免密码 root 和本地自动登录。
其他频段/安全模式的 Wi-Fi 验收范围，以及实际触控输入、长时充电、挂起、
音频、摄像头和蓝牙的状态，见状态文档。
