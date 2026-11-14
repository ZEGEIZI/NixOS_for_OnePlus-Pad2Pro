# Wi-Fi：OPD2413 原厂固件适配

2026-11-14：当前日常内核为官方 Linux `7.3.4-erhai-p5`；原生扫描、关联和联网已验收，见 [补丁集维护](KERNEL-PATCHSET.md)。
下文保留 2026-11-12 在 `7.2.15-nixos-erhai-efc39b9d9726-upstream4` 上定位固件路径的记录。
在此前分范围扫描修复基础上，按原厂 `BandCapability=3` 补齐 OPD2413 的 2.4/5 GHz
板级频率限制。普通全频扫描实测 9.58／9.81 秒完成，消除了此前 supplicant 的
20 秒超时取消；两轮各 100 次网关 ping 无丢包，一次 s2idle 恢复后自动恢复 5200 MHz。
固件和国家码处理沿用，当时保留旧 upstream3 与 brahma1 供回退。
详见 [原厂策略适配](WIFI-OEM-POLICY.md) 和 [扫描调查](WIFI-SCAN.md)。

同日进入当前原厂 Android 只读对照，已确认六个对应文件的 SHA-256 全部一致，
主机驱动、实际加载的 INI、国家码和信道列表则不同。
见 [Android 对照](WIFI-ANDROID-COMPARISON.md)；下面保留首次 `wifi1` 固件迁移的历史记录。

## 首次 wifi1 基线（历史记录）

2026-11-11：用户确认新方案已修复 5 GHz Wi-Fi。本项目将已安装、已启动验收的
`wifi1` 方案作为默认基线：保留 erhai Linux 7.2.15，应用 OPD2413 专用路径补丁，
使用已固定摘要的六文件原厂固件套件，并在 initrd 中提供完整配套固件。

本项目不受 ArmadaOS 模块化时采用的内核镜像大小预算约束，Wi-Fi 驱动栈明确
内建：`CONFIG_CFG80211=y`、`CONFIG_MAC80211=y`、`CONFIG_ATH12K=y`，
同时固定 `CONFIG_WLAN=y` 和 `CONFIG_WLAN_VENDOR_ATH=y`。
已验收的运行内核本来就是这些配置；现在将其显式写入 `packages/nixos.config`，
使后续构建不依赖上游默认值。现有配置检查器会在 Kconfig 合并后拒绝降为模块、
禁用或遗漏这些选项。固件仍由 initrd/系统固件包提供，不使用内核固件嵌入机制。

修复包含驱动路径、板级数据和配套固件的完整组合。后续更新内核或固件时，
应保留这些声明并重新验证目标热点的扫描、关联和数据传输。

## 与 ArmadaOS 的差异

对照的是 `armadaos-freedom/devices/oneplus-pad2pro/` 的 Linux 7.2.6 touch18，
不是该仓库的 `oneplus-pad2pro_mainline/`。迁移前项目使用 erhai Linux 7.2.15；相关设备修复现已前移到 7.3 补丁集，
初次迁移仅移植相关的设备固件路径适配；后续扫描修复见本文开头。

| 项目 | 原 NixOS 配置 | ArmadaOS touch18 / 本次移植 |
| --- | --- | --- |
| WLAN 主固件 | 通用 WCN7860 `amss.bin`，6,971,456 字节 | OPD2413 原厂版本，6,840,384 字节 |
| 其他固件 | 通用辅助固件、M3、QDSS 和监管数据库 | 同一原厂套件，逐文件大小和 SHA-256 校验 |
| 板级数据 | 通用 `board-2.bin`；虽打包 erhai 子目录，设备树未选择它 | 专用 `board.bin`，兼容 QMI board ID `0xff` 的回退 |
| 驱动请求路径 | `ath12k/WCN7860/hw2.0/` | OPD2413 + WCN7860 限定为 `ath12k/WCN7860/hw2.0/oneplus/opd2413/` |
| 扫描算法（初次 touch18 对照） | ath12k 扫描逻辑 | 当时未采用额外扫描算法补丁；后续已移植通用补丁集的分范围扫描 |

两份源码的 QMI 初始化和 WCN7860 硬件参数一致。7.2.15 的扫描请求多了
固件恢复期间返回忙的检查，监管代码也修正了频段索引和 single-pdev 的频率范围更新；
这些修复继续保留，不回退整份旧驱动。另一个差异是 NixOS 将 cfg80211/ath12k
内建，而 ArmadaOS 将它们编成模块；NixOS 的内建方案已实测通过，固件同步进入 initrd。

原文件的大小与哈希记录在 `inputs/firmware/wifi.json`，来自参考项目的
`inputs/firmware.json`；驱动补丁来自其 `kernel/current/upstream-to-touch18.patch`。
六个文件作为整套输入使用，旧通用与 erhai WCN7860 文件从安装清单和 initrd 清单中排除。
其他设备固件仍采用原有 erhai 上游清单。内核 release 后缀为 `-wifi1`，可区分旧内核。

## 固件输入

六文件 OEM 套件保存在随 Git 提供的
`inputs/firmware/archives/opd2413-wifi-firmware.tar`，普通构建自动读取和校验。
不需要 `inputs/local/`、手动打包或导入 Nix store。维护新固件的流程和许可边界见
[固件说明](FIRMWARE.md)。历史 `wifi1` 移植记录中的本机输入准备方式已被此方案替代。

归档 SHA-256 为 `c486e1c9e5caa56a49c746fdca4b098ceb355ae1426d5b66a60856540be8a8fc`。
成员、顺序和 tar 元数据固定，拒绝多余、重复、符号链接或损坏成员，
不会混用旧通用 WCN7860 文件，也不导入设备地址、配对密钥或其他运行状态。

## 构建与验证

```sh
nix flake check --no-build
nix build .#checks.x86_64-linux.wifi-firmware
nix build .#checks.x86_64-linux.boot-publication
nix build .#nixosConfigurations.pad2pro-build.config.system.build.toplevel -L
```

检查覆盖实际补丁函数的设备限定、整套路径选择和 `board.bin` 回退，
以及固件重复打包、摘要不匹配、重复/额外成员、符号链接和新旧固件混用。
安装到新代际的步骤见 `UPDATES.md`；旧代际保留作回退。

重启新内核后检查：

```sh
uname -r
nmcli -f SSID,CHAN,FREQ,SIGNAL device wifi list --rescan yes ifname wlp1s0
run0 iw dev wlp1s0 scan freq 5200 passive
```

本机问题的基线：电脑在 `Nwrt_5G_1`、信道 40（5200 MHz）、80 MHz 带宽关联；
旧 NixOS 扫描可见信道 149/153 的其他热点，未发现 `Nwrt_5G_1`，指定 SSID
重新扫描也没有发现。旧系统的驱动采用 world `00`、self-managed 监管域。
初次固件迁移没有修改国家码或移植分段扫描；后续在验证相同固件范围条件后，
已为 OPD2413 适配参考补丁，仍未强制国家码。

被动扫描是监管规则允许的正常扫描方式，本身不能证明热点缺失的原因。
参考项目保留的证据证明 Wi-Fi 联网，并未单独保存本热点信道 40 的扫描验收。
这次移植针对已确认的固件/BDF 差异；构建和自动检查通过也不能代替新代际
实机扫描、关联、DHCP 和数据传输验证。连接凭据由用户交互提供：

```sh
nmcli --ask device wifi connect "Nwrt_5G_1" ifname wlp1s0
iw dev wlp1s0 link
```

不要在关联期间用修改国家码替代该修复；上游记录此操作可能触发 WLAN 固件崩溃。

## 本次构建记录

完整 NixOS 系统、交叉编译内核及 kShimC 启动目录已构建通过；两个架构的
Flake 求值、20 项主机回归、实际驱动函数路径检查和 CPS8601 的 8 项故障场景通过。
实际系统和 initrd 内六个 OEM 固件的大小、SHA-256 均与清单匹配，旧 WCN7860
固件不存在；最终 DTB 包含 `oneplus,opd2413`，内核已编入 OEM 路径。

材料保存在 `artifacts/nixos-pad2pro-wifi1/`，包含配置快照、固定输入归档、
启动载荷与验证记录。系统为
`/nix/store/g2i4m0201kmnh7snvkbdxhgqkjq5w7gp-nixos-system-pad2pro-26.05.19800101.dirty`，
启动 ID 为 `nixos-7d5488900107d53c387d23c300031c25`。

2026-11-11 已按 kShimC 外置文件协议安装到设备，设为 current；previous 为
`nixos-c5d389974e65db7114fa0e40fa2ff8e0`，另保留 v6 普通版
`nixos-711a16405621b34c4e0809e735fa0d98`。系统 profile 已指向新闭包，
`/etc/nixos` 配置和固定固件输入已同步；原本机配置保留。设备原有配置与启动文件
备份在 `/var/lib/pad2pro-updates/wifi1-7d548890/`。

kShimC 项目原始 C 读取器已验证离线 ext4 内的新载荷；实机发布后逐项回读确认
清单、三份载荷摘要、GC root、六个原厂固件及匹配模块正常，旧版载荷保留，
共享菜单配置未改变，`/boot` 恢复只读，失败服务为 0。
记录在材料目录的 `installation.json`，安装包在 `install/`。
安装阶段使用 NixOS 的 `boot` 更新方式，没有主动重启设备。

## wifi1 实机启动与联网验收

用户随后手动重启进入新代际，SSH 实测运行内核为
`7.2.15-nixos-erhai-870167fad062-wifi1`，运行系统与已安装 profile 一致，
失败服务为 0，`/boot` 保持只读。扫描已发现 `Nwrt_5G_1`，信道 40、5200 MHz；
随后确认已关联该热点，通过 Wi-Fi 接口 ping 路由器三次均成功，
绑定 `wlp1s0` 的 HTTPS 请求返回 HTTP 200。原先漏扫的目标热点现已能扫描、连接和联网。

此次重启后 USB 链路曾暂时无法解析邻居地址，但电脑和平板两侧地址与路由均存在，
平板已到登录界面。通过 Wi-Fi 恢复管理，在电脑侧重新激活 USB 配置并检查收发后，
`192.168.77.2` 的 SSH 恢复；普通非混杂模式下双向 ping 无丢包，USB SSH 的
1 MiB 数据传输摘要正确。尚未确定最初收发停顿的具体原因，不能据此认定已永久修复
USB 重枚举问题。当前也可通过 Wi-Fi 地址 `192.168.2.206` 管理，该地址由 DHCP 分配。

新固件关联后的实测监管状态为全局 `00`、phy0 self-managed `US`；此过程未执行
手工国家码修改命令。该状态只描述本次 NixOS 运行样本，不能反推旧 ArmadaOS 的状态。
记录见材料目录的 `first-boot.json` 和 `wifi5-connectivity.txt`。
