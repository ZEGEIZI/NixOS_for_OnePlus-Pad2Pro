> 本文保留 7.2.15 移植验收记录；当前驱动由独立补丁集维护，见 [KERNEL-PATCHSET.md](KERNEL-PATCHSET.md)。

# OPD2413 原厂蓝牙方案

本次将 ArmadaOS successful29 的 Brahma 2.0 初始化与本机原厂固件移植到
Linux 7.2.15，并沿用 NixOS 的工厂地址自动读取服务。候选配置为
`pad2pro-brahma`，内核后缀为 `brahma1`；已完成原厂加载、连接与播放验收，
并提升为日常 `pad2pro` 的冻结基线。

## 为什么需要成套切换

旧驱动把本机作为通用 WCN7860，加载 ROCKNIX 分发的 `gngbtfw20.mbn` 和
`gngbtnv20.bin`。原系统日志出现 `-84` 接收重组错误、`0xfc00` 超时及重试；
本次读取的旧启动约 187 秒才完成 setup，不能把扫描可用等同于初始化稳定。

原厂 Brahma 流程先加载 Peripheral patch/NVM，再加载 TME-L、激活 Bluetooth，
最后加载 Bluetooth patch 与按 board ID 选择的 NVM。UART 从 115200 切到
8000000，必须配合 RX DMA 先准备缓冲、切速时停收/恢复、自动 CTS/RFR 及
本机直接 GCC 时钟选择处理。只改固件名或替换主蓝牙文件不能完成迁移。

## 源码与发行版职责

驱动、设备树、绑定和协议自测维护在共享 `linux-sm8750-erhai` 仓库。
新增 `oneplus,opd2413-brahma20-bt` 类型，保留通用 `qcom,wcn7860-bt` 路径。
移植保留 Linux 7.2.15 已有的 IBS power-off、UART suspend/resume 与带宽行为，
没有用较旧参考文件覆盖整个驱动。UART 大量诊断日志未移入，协议诊断有次数上限。

参考来源为 ArmadaOS `937d88a2c28a67153d572bcf7f89049eaada93f2` 的
`devices/oneplus-pad2pro/kernel/current/final-modules/`，保留 GPL-2.0-only
和原驱动版权声明。NixOS 当前固定源码仍是 `40f9157a…`，通过
`docs/history/kernel/patches/opd2413-brahma-bluetooth.patch` 应用共享树的运行时变更，
避免依赖另一工作目录或未发布的远程提交。来源及共享文件摘要保存在同目录
`.source.json`；绑定、内核文档及协议自测在共享仓库维护。

`hardware.oneplus-pad2pro.stockBluetoothFirmware` 与内核的
`opd2413StockBluetooth` 标记必须同时选择，否则系统求值拒绝构建。
`modules/oneplus-pad2pro.nix` 负责固件包和 initrd；驱动代码不依赖 NixOS。
原有 Ganges 文件可作为旧驱动配置的输入保留，但 Brahma 类型只请求 OEM 路径，
缺固件时失败，不静默退回 Ganges 或裸 ROM。

## 固件输入与设备身份

`inputs/firmware/bluetooth.json` 固定 14 个文件的名称、大小和摘要。
包括主 Bluetooth MBN、默认及九个 board NVM、Peripheral MBN/NVM、TME-L ELF；
不打包未使用的主 Bluetooth TLV。当前归档随 Git 保存在
`inputs/firmware/archives/opd2413-bluetooth-firmware.tar`，构建自动读取和校验，
无需本机固件目录或手动导入；见 [固件输入](FIRMWARE.md)。

归档 SHA-256：`a7343f5cc4db8f717ea2ab3dc4c665358ffd1fad9ffb97f4c5dbce2a6d8d4df5`。
解包前完整验证成员、类型、大小和内容摘要，拒绝多余、重复、符号链接、缺失及损坏成员。

十份 Bluetooth NVM 使用同一发行版默认地址占位符，已核对不同于本机工厂地址。
本机身份仍由 `/var/lib/oneplus-pad2pro/bt-address` 及 `nonmodemst1/2` 的只读
解码服务提供；不把工厂记录、真实地址或配对密钥写进归档、Nix store 或通用镜像。

## 构建与实机验证

- 原厂 14 文件逐份校验并可重现打包，ARM64 固件包构建成功。
- 62 项 Python 回归通过，包含坏固件归档的原子拒绝。
- 实际 `brahma_peripheral.h` 的主机 C 回放测试在 ASan/UBSan 下通过：完整初始化、
  每一步畸形响应及超时、所有发送失败、错误 ROM/状态/板号及无效固件格式。
- 候选完整系统求值通过，保留 HDR 桌面和内置音频模块；旧内核搭配 OEM
  固件的负对照被匹配断言拒绝。

本次 NixOS 已完成三次真实重启（第三次由用户主动发起），首次 setup 分别在
开机 2.607 秒、2.519 秒、3.632 秒完成，未见旧组合的 `-84` 重组错误、`0xfc00` 超时或重试。Peripheral/TME-L
加载成功，实际请求 OEM `brhbtfw20.mbn` 和 `brhbtnv20.bin`，没有请求 Ganges。
地址服务两次成功，沿用本机工厂身份及既有配对；没有手工重新配对。
第一轮 FIIO 已成为默认 A2DP/LDAC 输出，用户确认音乐正常、没有卡顿或断连；
后续启动保留配对，手动连接后用户再次确认播放正常。虽然状态采集时检测到
FIIO 已连接，用户明确报告需要手动连接，因此自动重连不能判为通过。
FIIO 为 Trusted，适配器已上电且 BlueZ `AutoEnable=true`；问题来自
PipeWire 默认未启用启动连接，后续已补入 WirePlumber A2DP 自动连接规则，
并经真实重启及用户确认通过，见 [蓝牙自动连接](BLUETOOTH-AUTOCONNECT.md)。
5 GHz 信道 40 联网、网关 ping 与 HTTPS 通过，
内置音频 sink/source 保留，系统与用户失败服务均为 0。

当前完整系统为 `/nix/store/g774yvbkc5h0jp9gvhyzb2632p3m5sri-nixos-system-pad2pro-26.11.20261107.f4a03c0`，
启动代际 `nixos-80c6521597b673e4d69d3c6d0644463e`。日常与候选配置产生相同
系统闭包。`docs/history/kernel/validated-kernel.json` 和 `docs/history/kernel/configs/brahma1.config`
固定本次验收产物；显式新内核构建仍使用当前 `packages/nixos.config`。
旧 color1/wifi1 的包定义与原冻结配置没有删除。

尚未验证：断电冷启动、Android 切回、长时间播放、通话麦克风和挂起恢复。
不能将正常重启与短时听音表述为这些场景全部通过。
结构化证据见 [验收清单](BLUETOOTH-OEM-VALIDATION.json)。
设备上的构建及调试记录位于 `/var/lib/pad2pro-updates/bluetooth-oem/`。
按用户要求不创建备份；本轮先前创建的配置备份已删除。
