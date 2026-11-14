# 适配状态

2026-11-13 正在迁移到官方 Linux 7.3.4 + 独立设备补丁集，当前代码及验收进度见
[补丁集迁移](KERNEL-PATCHSET.md)。本文以下的 fork 包名、固定源码及历史闭包属于
对应日期的记录，已移除的旧构建入口不代表当前 flake；本轮尚未切换实机默认内核。

2026-11-13 HDR 入口整理：移除 10bit/12bit、灰阶诊断、SDR/原生播放器模式等
功能型 `.desktop` 条目，只保留标准 mpv 应用入口；视频默认关联改为 `mpv.desktop`，
由内部脚本自动处理 HDR。精度切换和诊断继续使用 `pad2pro-display`、
`pad2pro-hdr-check` 脚本，所有账户共用。此前新增的模式及诊断菜单入口已撤回。

2026-11-13 多账户 HDR：默认网页和视频入口改为系统级 MIME 配置，新增自动
HDR/SDR 视频播放器及所有账户共用的“HDR 高光测试”。测试资源带完整 BT.2020/PQ
标签，不依赖旧账户家目录、网站选项或播放器参数。当前新账户以空白客户端配置
通过 10bit、12bit 两组画布/视频测试，背光均为 1053 → 2047 → 1053；用户确认
三行画布与视频都能看到高光层次。TestUFO Canvas 2D 的 SDR 映射与未标注色彩的旧
FFV1 诊断片已明确区分。见 [所有账户共用的 HDR 入口](DISPLAY-COLOR.md)。


2026-11-13 Chromium 参数警告：将开发者专用 `--enable-blink-features` 改为
四项同名 HDR `--enable-features` 开关。原生浏览器界面对照确认警告消失，
HDR/30-bit、普通网页与高光背光升降、TestUFO WebGL/PQ 均复查通过。


2026-11-13 Chromium 背光修复重做：撤回禁用浏览器 HDR 的 SDR 临时方案。
Chromium 恢复 Wayland HDR 与 Canvas API，Mutter 在 XN242 HDR 模式下改为
向客户端首选 PQ，区分编码范围和目标显示峰值，保留实际面板 Gamma 输出。
构建、编译后色彩转换及实机会话测试通过：普通网页背光 1467，实际高光
1987，移除后 1468；浏览器保留 HDR/30-bit。TestUFO WebGL/PQ 高光和
SDR ↔ HDR 检测均通过。完整验收记录见
[显示与 HDR](DISPLAY-COLOR.md)。

2026-11-12 原厂 WLAN 策略：日常内核更新为 `upstream4`（`efc39b9d9726`），
按实际 Android 配置与一加公开源码限定 OPD2413 为 2.4/5 GHz。普通全频扫描
9.58／9.81 秒正常完成，消除此前 supplicant 20 秒超时；两轮共 200 次网关 ping 无丢包。
一次 s2idle 恢复后自动恢复 5200 MHz 和数据传输，频段限制保持。用户确认显示、触控、
音频和蓝牙正常；upstream3 与 brahma1 保留回退。见 [原厂策略验收](WIFI-OEM-POLICY.md)。

2026-11-12 上游合并及 5 GHz 启动发现：日常内核升为 `upstream3`（共享源码
`c3583ea3a35f`），保留原 OEM Wi-Fi／蓝牙固件。适配 ArmadaOS 分范围扫描后，
临时启动和普通共享分区启动在首次观测的 24.10／33.28 秒均已自动连接 5200 MHz。
用户确认显示、触控、蓝牙播放正常。旧 `brahma1` 的冻结配置、闭包和启动回退保留。
关联全频扫描约 20 秒被取消的发起方待查；期间 100 次网关 ping 无丢包、未断连。
详见 [Wi-Fi 扫描调查](WIFI-SCAN.md) 和 [内核维护](history/KERNEL-SOURCE.md)。

2026-11-12 蓝牙开机自动连接：补入 WirePlumber 原生 `bluez5.auto-connect`
A2DP 策略，解决 AutoEnable 只开适配器、PipeWire 默认不主动连接的缺口。
WirePlumber 启动自动连接和真实整机重启均通过，FIIO 默认输出为 A2DP/LDAC；
用户明确确认未手动点连接、播放正常。冻结内核与启动载荷沿用，失败服务为 0。
详见 [蓝牙自动连接](BLUETOOTH-AUTOCONNECT.md)。

2026-11-12 原厂蓝牙切换：已移植 ArmadaOS Brahma Peripheral/TME-L、8 Mbps
UART 与本机 OEM 固件，日常内核升为 `brahma1`。三次正常启动首次 setup
分别为 2.607/2.519/3.632 秒，未见旧组合的接收重组错误或初始化超时。
FIIO BTR13 A2DP/LDAC 音乐经用户确认正常，手动重连后也能播放；固件切换阶段自动重连
尚未通过，后续已由上面的 WirePlumber 策略修复。5 GHz Wi-Fi、原厂地址服务及内置音频枚举
正常，系统和用户失败服务为 0。62 项回归、协议故障回放、完整构建和启动
载荷校验通过。按用户要求不保留本轮临时备份。详见 [原厂蓝牙方案](BLUETOOTH-OEM.md)。

2026-11-12 内置音频：补入缺少的 AudioReach 拓扑与本机 UCM，声卡注册成功。
GNOME 显示扬声器和麦克风，用户确认左右声道听音与说话输入电平均正常。
采用保守功放增益，原厂 DSP 扬声器保护仍未实现。完整系统构建、60 项回归、
三个启动代际载荷校验通过；冻结内核、模块、DTB 和原 77 个固件保持一致。
修复已在线启用并持久发布，重启、独立录音回放与挂起恢复待验收。
详见 [内置音频](AUDIO.md)。

2026-11-12 GNOME 充电保护：补入本机电池的 udev `CHARGE_LIMIT` 元数据，
UPower 由不支持变为支持，原生电源设置可使用充电模式。D-Bus 下发首次 75/80、
94% 电量停充及取消限充恢复充电均已实测；GNOME 设置的默认权限通过。
当前保留充到 100% 的模式。内核对起充 0 的夹取会导致 UPower 重启后可能
沿用 50% 恢复点；挂起限充及完整阈值放电恢复仍未验收。详见
[GNOME 充电保护](GNOME.md#gnome-充电保护2026-11-12)。

2026-11-12 蓝牙首次安装自动初始化：已追踪 Android 的原厂地址读取链路到
`nvram_server` / `nvram_qmi` 与 `nonmodemst1/2` 冗余工厂分区。独立只读解码、
双重摘要、Android/Linux 地址交叉核对均通过。新服务从标准 socinfo 获取本机标识，
无需预置地址即可配置 hci0；空状态实机测试、29 项蓝牙及全部 52 项回归通过。
新配置已持久发布为 `nixos-06f3e4b35a208da7db344a74adbfc516`，按用户要求删除
最旧 HDR v1 启动版本，保留菜单 8 项；77 个固件文件摘要与变更前一致。
已删除地址缓存并正常重启新代际，服务约 1.9 秒自动恢复原厂地址，扫描到 7 个设备，
失败服务为 0。配对/重连与第二台设备仍待实测，详见 [蓝牙适配](BLUETOOTH.md)。

2026-11-12 蓝牙早期修复（已被上面的自动初始化方案替代）：已定位 GNOME 无法开启的直接原因是 WCN7860 缺少本机
`public-address`，控制器停在 Unconfigured。保留已验收 color1 内核和固件，
移植 ArmadaOS 的单机地址初始化逻辑，补入此前与 Android 核对的本机地址后，
BlueZ 开启成功，用户确认 GNOME 已能开启并扫描到设备。
当时服务发布至 `nixos-2af73f38e20880389bdde24bbabf14bd`；12 项回归、
系统构建和服务重复执行通过。当时重启自动初始化、配对和音频仍待验收。
详见 [蓝牙适配](BLUETOOTH.md)。

2026-11-11 后续：按用户功耗测量，配置改为默认 10bit HDR，保留同会话手选
12bit HDR；新增按实际画面最大值调节背光、最终像素补偿和元数据感知 Tone
Mapping。Adreno 830 上单像素高光归约、白位补偿 GLSL、原 FRC 精度测试通过。
重新登录后的会话已验证两种精度切换、HDR 重新开启默认 10bit、HDR 滑块真实
控制背光及 SDR 背光恢复。32×32 高光让背光 1207 → 2042 → 1207，参考白
设定不变，用户确认大白块目视“基本稳定”。绝对光学亮度仍未校准。
发布代际为 `nixos-5f264e38a87b90becf4b3fe8ad8d8cde`，系统 profile 已指向
`a1jf5iv4fw7mfyhrgk3r6pzas6mhyb59`，前一代及冻结内核仍保留。
用户报告原实现 SDR 最大/最小约 11/2.3W，HDR 12bit 约 15.3W、HDR 10bit
约 11.1W，HDR 滑块不改变背光耗电；这些是用户实测记录，不是自动化基准。

2026-11-11 HDR + 8+4-bit 联合候选：已构建并发布
`nixos-41550284093e0d1dd8a81eaed8dae245`，系统为
`hg886m24jlny3ychb1v1klardvwhgjqp`，保留 color1 内核和原回退代际。
此前该候选默认 `pad2pro` 启用 FRC，`pad2pro-hdr10` 保留不启用 FRC 的 HDR 对照。
修正 Gamma FP16 中间缓冲丢失细分值的问题，使用 UNORM16、FP32 回退。
Adreno 830 上覆盖中间缓冲的 FRC GPU 检查通过；FP16 负对照失败，两个修正格式
均为零误差。新原生播放器已验证 AB48 16-bit Wayland 提交；真正的 HEVC
12-bit / BT.2020 / PQ 测试片已解码验证。23 项现有回归、全部系统的 Nix 求值和
五个启动代际的载荷摘要校验通过。注销并重新登录后，实际加载新 Mutter，
HDR 与 UNORM16/FRC 同时运行，XR30 扫描、两路 DPU 抖动均确认。
最近 30 个帧率采样的中位数为 119.95 FPS，范围 116.60～120.03 FPS，接口
underrun 为 0。HDR → SDR → HDR 切换通过；系统与用户失败服务均为 0。
用户确认五块 HDR 灰阶均能区分，渐变稳定且没有明显闪烁或颗粒。
测试图、生成脚本和一键打开入口已保存到平板 `~/图片/HDR与12bit测试图/`。
绝对亮度、面板光学有效位数及持续功耗尚未测量。详见
[联合候选](DISPLAY-COLOR.md#hdr-与-84-bit-联合候选2026-11-11)。

2026-11-11 早先的 HDR 续查：用户已确认原生播放器在 GNOME HDR 关闭时只见两级灰阶，
开启后五级均能清楚分辨。当时回到常规 10-bit 合成，8+4-bit 和背光候选改动未启用。
用户随后确认 Chromium 同屏的三种 PQ Canvas 和 HDR 视频四行均能分辨五级。
用户进一步确认 TestUFO 的 WebGL 可见 HDR，而 Canvas 2D 不可见。实机读回与
Chromium 源码确认：Canvas 2D 默认 HDR headroom 为 0，将 HDR 图像高光映射回 SDR；
WebGL 使用 extended HDR 和 RGBA16F，保留约 2000 nit 对应的内容高光编码。
验收指引与诊断工具已改用 WebGL；此前“网站没有高光输入”的判断已更正。
协议的峰值/白位差异仍保留排查记录；未部署新的 Mutter。新增的同屏
灰阶及 TestUFO 诊断工具已经实机执行。HDR → SDR → HDR 的切换复查通过：
浏览器分别报告 SDR/24-bit、HDR/30-bit，结束后恢复原 HDR 模式与 70% 参考白滑块。
用户要求本轮只处理 HDR；背光候选已从活动配置撤回，编译期间发热不足以诊断背光故障。
详见 [Chromium 排查](DISPLAY-COLOR.md#chromium-157-亮度描述排查2026-11-11)。

2026-11-11 夜灯黑屏恢复：夜灯开启后黑屏、登录时复现。已在用户及 GDM dconf
配置中关闭并锁定夜灯，关闭状态重启后用户确认桌面恢复。修复代际
`nixos-8d39778e37ce5247a25782f9654143f5` 已真正启动并登录，夜灯状态为 false、
6500K，系统和用户失败服务均为 0。恢复过程中误写的 kShimC 默认项已纠正，
原 Android 默认值已恢复，实际启动载荷通过原始读取器校验。
夜灯暖色功能仍待图形栈适配，普通深色主题不受此锁定影响，详见
[夜灯黑屏恢复](GNOME.md#夜灯黑屏恢复2026-11-11)。

2026-11-11：GNOME 51.0 Wayland 已部署并在线启用，`nixos` 账户已通过 GDM 登录，
seat0 会话处于 active。用户空间采用最新 `nixos-unstable` 的 `f4a03c008967`，
设备内核、模块和 DTB 保持原已验收版本。内屏 3392×2400 / 120 Hz / 200% 缩放；
Mesa 26.2.6 的 Adreno 830 绘制回读、4,000 次共享上下文压力测试通过，Vulkan
识别为 Turnip。中文字体、IBus 拼音、Firefox 159.0.1 和 PipeWire 已配置。
系统和用户服务均无失败；USB SSH、Wi-Fi 保持正常。
新启动代际已发布，但未重启验证新 initrd。详情、硬件边界和更新方式见
[GNOME 桌面](GNOME.md)。下面的基础适配和表格为桌面升级前的历史记录。

内核源码已迁移至 ZEGEIZI fork；日常维护复用已验证闭包，显式新内核构建使用
已集成补丁的固定提交。两条构建路径见 [内核源码与维护](history/KERNEL-SOURCE.md)。

2026-11-11：用户已确认 5 GHz Wi-Fi 修复，wifi1 方案固化为默认基线。
cfg80211、mac80211、ath12k 显式内建，已验收的运行内核也是内建配置。
当前固定原厂固件输入随 Git 保存在 `inputs/firmware/archives/`，构建时按清单和归档摘要自动校验。
已移植 ArmadaOS touch18 的 OPD2413/WCN7860 专用固件路径，
并将原厂六文件套件纳入 Nix 的固定输入和 initrd，排除旧通用固件。
实机旧系统漏扫 `Nwrt_5G_1`（信道 40），但能发现信道 149/153 热点；
完整系统及启动目录已构建，实际 initrd 六个固件摘要、20 项主机回归、驱动路径
检查和 CPS8601 的 8 项故障场景通过。材料在 `artifacts/nixos-pad2pro-wifi1/`。
新代际 `7d548890…` 已安装并设为 current，previous 为 `c5d38997…`，
v6 `711a1640…` 同时保留。设备载荷、固件摘要、模块、GC root 和只读挂载通过核查；
系统 profile 指向新闭包，原配置和启动文件已备份，失败服务为 0。
用户随后已重启，新内核和对应系统闭包实机启动通过；`Nwrt_5G_1` 的信道 40 扫描、
关联、路由器 ping 及 HTTPS 联网通过，失败服务为 0。USB 曾短暂无法解析邻居地址，
检查后 SSH 恢复，普通模式双向 ping 与 1 MiB 传输通过；首次停顿原因仍待定位。
实机证据为材料目录的 `first-boot.json`；以下历史记录主要描述更新前版本。
差异、输入准备与验收方法见 [Wi-Fi 说明](WIFI.md)。

2026-11-10：OnePlus Pad 2 Pro OPD2413（16 GB）的基础 NixOS 26.05 适配与安装
验证已完成。系统不含桌面，使用内核 `7.2.15-nixos-erhai-870167fad062`。
已通过持久 kShimC 菜单完成 Android → NixOS → Android 往返；随后按用户要求重新执行标准安装及磁盘检查；用户最后确认
当前代显示 `pad2pro login:`，已安装系统的 USB SSH 主机身份再次验证通过。用户随后交互设置了 `nixos` 密码，并确认 USB SSH 登录成功；root 账户仍锁定。

| 项目 | 当前证据 |
| --- | --- |
| 启动链 | kShimC → 内核 → NixOS systemd initrd → Btrfs 系统 → 文本登录，实机通过 |
| 持久菜单 | boot_a 使用 `KShinC_BOOT`，完整读回摘要匹配；普通当前代、前一代和 Android 均已启动；boot_b 未修改 |
| 分区 | `KShinC_BOOT` 1 GiB ext4；`NixOS_Root` 200 GiB Btrfs；Android userdata 约 258.97 GiB；主、备 GPT 校验通过，分区 1～14 表项逐字节保留，分区 GUID 均保留 |
| 运行时挂载 | PID 1 挂载表确认 root/nix/home/log 四个 Btrfs 子卷；`/nix/store` 只读绑定，ext4 `/boot` 只读 |
| USB NCM / SSH | 普通当前代及前一代均已连接，SSH 主机密钥与安装文件系统一致；用户已验证 nixos 密码登录 |
| 基础服务 | wifi1 实机启动后 0 个失败服务，登录、USB SSH 和 Wi-Fi 联网通过 |
| 手选回退 | v6 已完成手选回退；当前 wifi1 `7d548890…`，previous 为 `c5d38997…`，额外保留 `711a1640…` |
| 安装与 GC | wifi1 签名闭包导入和三个代际 GC roots 已核查；profile 历史保留；本轮未运行 GC，GC 后启动证据仍来自 v6 |
| 启动文件发布 | wifi1 通过原始 kShimC C 读取器及实机发布检查；三个保留代载荷摘要正常，/boot 约 246 MiB、只读 |
| CPU 调频 | SCMI v2.0，两组策略均使用 scmi + schedutil，最高频率分别 3.5328 / 4.0896 GHz |
| CPU idle | `psci_idle`，读到 WFI 和 cpu-sleep-0 累计驻留时间；整机挂起恢复未验收 |
| zram | 物理可用内存的 50%，实机约 7.3 GiB、zstd；2026-11-13 已在线调整并持久化，swap 已启用 |
| 显示 | 3392×2400 msmdrmfb，tty1 活跃；framebuffer 与用户观察均确认文本登录提示 |
| Wi-Fi | wifi1 实机已扫描并连接 Nwrt_5G_1（信道 40 / 5200 MHz），经 wlp1s0 的路由器 ping 和 HTTPS HTTP 200 通过 |
| ADSP / SoCCP | 日志确认启动完成 |
| 触控 | 固件加载成功，触屏与笔输入设备已注册；实际输入未验收 |
| 电源与温度 | v6 诊断样本为电量 94%、31°C、Charging、正向电流 37232 µA；温度传感器可读，长时充电和快充未验收 |
| 构建检查 | Flake 全系统求值、安装缓存签名、20 项主机回归和驱动路径检查通过；显式内建声明生成的完整配置与实机验收版逐字节一致；平板本机完整内核编译尚未实测 |

普通当前代为 `nixos-7d5488900107d53c387d23c300031c25`，材料目录为
`artifacts/nixos-pad2pro-wifi1/`。前一代为
`nixos-c5d389974e65db7114fa0e40fa2ff8e0`，材料目录为
`artifacts/nixos-pad2pro-install-v7/`；v6 `711a1640…` 额外保留。各目录的 `installation.json` 记录实际
系统路径及验证结果，`config/` 是构建时的冻结源码快照，包含本机 boot PARTUUID。
已安装配置位于 `/etc/nixos`；日常使用普通“当前代 / Current”。

当前和前一代普通版均默认关闭 HTTP 诊断。此前带只读 USB 状态接口的诊断代
已从启动菜单和 `/boot` 删除。菜单手选仅改变当次启动；尚未在平板上
实测 `nixos-rebuild --rollback` 的 profile 回退、断电故障注入、受控关机/重启
或完整断电冷启动。普通账户的密码 SSH 登录已经用户实际操作验证。

Android 最初从新菜单及临时原厂 boot 均进入 recovery，标准 BCB 中没有
`boot-recovery` 指令。用户随后在原厂 recovery 手动清除数据，Android 恢复启动；
之后持久菜单往返验证通过。确切失败的文件系统或加密初始化环节未取得日志，
尚未通过 ADB 测量 Android 文件系统容量。首次 fastboot erase 的 OKAY 不能替代
原厂数据区重建和实机启动验证。本轮诊断未由工具再次擦除 userdata/metadata。

实施中修复了三个问题：initrd 补入并加载 `qcom-cpucp-mbox` 以完成 SCMI 初始化；
内核加入 `CONFIG_NETFILTER_XT_MATCH_PKTTYPE=m` 以使防火墙正常启动；USB gadget
改为 initrd 绑定，使普通系统能够枚举。安装器使用 `python -B`，避免在安装时的
可写 Nix store 产生字节码缓存；修复后重复发布及整个 store 内容校验通过。

可选的笔充电升级固件未打包，芯片内置 `0x011e` 已正常运行，重复报错由匹配模块
修复；实际笔充电仍未验收。已知限制还有音频 topology 缺失、摄像头探测失败和
蓝牙启动期错误；基础系统不配置扬声器。wifi1 的 5 GHz 联网已验收，实际触控、
长期充电、快充及挂起恢复也尚未验收。平板时钟未完成网络校时。

USB 启动期可见 SuperSpeed 枚举重试并回退 High-Speed。完整 RAM 系统曾有一次
下载中断而进入 initrd 紧急模式；精简只读诊断及已安装系统的 USB 访问均已验证，
长期传输稳定性仍需观察。`amba ... deferred probe pending` 在普通系统到达
多用户目标后也会出现，不能仅凭这行判断系统卡死。

已部署菜单 SHA-256：
`797dd06f054b24b7d94b20d703a8357ba3e6bcce2e3900bf2f163564c6f14174`。
当前 RAM v2 维护镜像 SHA-256：
`632fe0d303959ac9856d19398054057cac2ff10c5be48470454ad88a0e019ca5`。
首次交付时已清理电脑端临时 HTTP 服务和 USB 调试连接；后续教程排障已重新开启。
此次 RAM 启动失败时电脑缺少 USB IPv4 地址和文件服务，恢复两项后重启通过；
SSH、tmpfs/overlay/squashfs 挂载、下载摘要和登录服务均已验证。完成密码设置后
文件服务已停止；下次使用 RAM 前按 `TUTORIAL.md` 重新准备，日常 SSH 无需该服务。
详细机器可读证据及私有日志索引见 `validation.json`；备份和诊断材料保留于 `.work/`。

按用户选择，当前 RAM 维护系统已改为 USB 免密码 root 登录和 tty1 自动登录，
两项均已实测；SSH 仅监听 `192.168.77.2`。RAM v2 镜像及配套文件已实机启动验证，
免密码 SSH、本地自动登录、文件校验均通过，失败服务为 0；配置隔离和 12 项
主机测试也已通过。RAM 模式没有解锁普通安装账户；之后用户单独设置了 `nixos` 密码，root 继续锁定。详见
`RAM-SYSTEM.md` 与 `artifacts/nixos-pad2pro-ram-system-v2/access.json`。

CPS8601 可选固件重复报错修复已安装为 v7：普通当前代 `c5d38997…`，
只读诊断版 `9bb09c19…` 曾保留用于验证，现已清理。模块构建、8 项模拟故障测试、
12 项发布测试、签名缓存、实际六条启动记录及全量安装 store 校验均通过；
实机诊断报告已确认修复模块加载，原五条固件缺失错误为 0，芯片 `0x011e`、
ready 和扫描正常，失败服务为 0；普通当前代也已完成登录与 USB/SSH 验证。
实际笔充电尚未验收；外置模块提示是预期标记。详见 `CPS8601.md`。

正式系统 USB SSH 密码登录已完成：电脑执行 `ssh nixos@192.168.77.2`。
电脑的 `pad2pro-usb` 网络配置已保存到磁盘，同一 USB 口会自动使用
`192.168.77.10/24`。RAM 下载文件服务已停止，日常已安装系统的 SSH 不依赖它。

用户执行已演练的清理脚本后，四个旧启动目录和对应 GC roots 已删除；现仅保留
当前 v7 普通版与 v6 普通回退版。释放 338907136 字节（约 323 MiB），`/boot`
使用率从 54% 降至 19%，只读挂载已恢复；本次没有重新启动或运行 store GC。
