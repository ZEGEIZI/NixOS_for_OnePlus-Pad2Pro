# Wi-Fi：Android 原厂实现对照

2026-11-12 已进入本机 `OPD2413_16.0.9.400(CN01)` Android 16 采集资料。
没有修改原厂固件、国家码、INI、模块或保存的网络配置；执行了一次普通扫描。
不含地址和网络名称的摘要见 [实测数据](WIFI-ANDROID-REFERENCE.json)。

## 固件相同，主机驱动不同

六个当前 NixOS 固件文件的 SHA-256 均与 Android 对应文件一致：

| NixOS 文件 | Android 对应文件 |
| --- | --- |
| `amss.bin` | `/vendor/firmware_mnt/image/peach/amss20.bin` |
| `aux_ucode.bin` | 同目录 `aux_ucode20.elf` |
| `board.bin` | `/odm/etc/wifi/peach/bdwlan.elf` |
| `m3.bin` | `/vendor/firmware_mnt/image/peach/phy_ucode20.elf` |
| `qdss.cfg` | 同目录 `qdss_trace_config_v2.cfg` |
| `regdb.bin` | 同目录 `regdb.bin` |

Android 启动日志也确认了 `amss20.bin` 和 ODM BDF 的实际加载路径，
不能拿 vendor 目录下另一个同名 `bdwlan.elf` 代替 ODM 覆盖文件。

固件运行在无线芯片上；主机驱动运行在应用处理器上，负责初始化芯片、选择硬件模式、
构造扫描命令及处理结果。相同固件接收不同命令和配置，结果可以不同。

| 层次 | 当前 Android | 当前 NixOS |
| --- | --- | --- |
| 内核 | Android 6.6.118 | erhai 7.2.15 / upstream3 |
| WLAN 主机驱动 | `qca_cld3_peach_v2`，PCI 平台层 `cnss2` | `ath12k_wifi7_pci` / ath12k / mac80211 |
| 上层控制 | Android Wi-Fi 框架、厂商 HAL | NetworkManager 和 Linux 无线栈 |
| 国家码样本 | 运行时 `CN` | global `00`、self-managed PHY `US` |
| 信道能力样本 | STA 列表含 2.4/5 GHz，没有 6 GHz | PHY 和此前扫描记录包含 6 GHz |

这不能归因于 Nix 包管理本身；使用相同驱动、固件和配置的其他发行版也可能遇到同样问题。

## 实际加载的原厂配置

`ueventd` 日志确认加载的是 `/mnt/vendor/persist/wlan/WCNSS_qcom_cfg.ini`，
其摘要为 `3037434c5af0200cd23e6779f07054d3d9c544b5deeb25856bec9039df8e5420`。
它与 `/vendor/etc/wifi/peach_v2/WCNSS_qcom_cfg.ini` 模板不同，不能只读模板就推断运行行为。

实际加载文件包含：

```ini
g11dSupportEnabled=0
enable_sbs=0
BandCapability=3
gCountryCodePriority=1
adaptive_dwell_mode_enabled=0
hostscan_adaptive_dwell_mode=1
gInitialScanNoDFSChnl=1
```

这是配置输入的证据，尚不等于逐项确认固件最终执行的模式。模块参数 `enable_11d=-1`
也不能独立证明 11d 已启用或禁用。后续已在一加公开的 Android 16 Pad 2 Pro 源码 `cc463675855afb…` 中确认
`BandCapability=3` 明确表示仅 2.4 GHz 和 5 GHz，与实机信道列表一致。
具体来源和驱动改进见 [原厂频段策略适配](WIFI-OEM-POLICY.md)。
`gInitialScanNoDFSChnl=1` 本身不能解释信道 40 漏扫，因为该信道不属于 DFS 信道。

Android 本轮已关联 5200 MHz。普通扫描请求成功，8 秒后缓存有新结果，仍保持 5200 MHz
关联；没有测量精确的全频扫描完成时间，不能把 8 秒写成完整扫描耗时。

## 当前 Linux 修复及后续判断

Linux 对照实验确认：旧路径的全频扫描正常报告完成，访问过 5200 MHz 却没有发现目标；
单独扫描 5200 MHz 则立即发现并自动连接。固件报告 DBS_OR_SBS 模式，两组 PHY 范围为
4900–5320 和 4900–7125 MHz，而驱动对上层呈现一个逻辑 radio。

`upstream3` 按固件边界拆分扫描请求，关联时采用受 TX 排空保护的单信道批次；另保留
扫描优先级赋值、监管回复 completion 和扫描超时生命周期修复。
两次启动在首次观测的 24.10／33.28 秒均已自动连接目标，详见 [扫描调查](WIFI-SCAN.md)。

目前没有证明 Android 恰好使用与此补丁相同的分批算法，也没有完全还原原厂 WMI 命令序列。
原厂硬件模式选择、信道能力、驻留策略和国家码初始化是更有针对性的后续对照点，
后续已捕获 wpa_supplicant 的 20 秒超时主动取消日志；同一个 supplicant 的
36 信道 2.4/5 GHz 对照请求约 9.2 秒正常完成。按原厂能力限制的候选内核正在验证，
详见 [原厂频段策略适配](WIFI-OEM-POLICY.md)。

参考原厂实现适合本设备的协议和策略有价值。直接复制 Android `.ko` 不能替换当前驱动：
本机模块的 vermagic 是 `6.6.118-android15-8-o-4k`，还依赖 CNSS/QCA 公共层、
厂商内核接口及上层控制。整套驱动移植需要适配当前内核；改用 Android 内核运行 NixOS
则属于另一条完整适配路线，Wi-Fi 正常不能替代其他硬件验收。
因此目前保留已验收的 upstream3，用原厂证据指导后续驱动改进，没有盲目复制 INI 或强制国家码。

采集后已从共享启动分区返回日常 upstream3，系统路径与已验收闭包一致，
仍关联 5200 MHz，网关和 HTTPS 检查通过，无失败服务、严重内核错误或蓝牙初始化错误。
本轮首次观测较晚（158.08 秒），不能据此计算连接耗时。
