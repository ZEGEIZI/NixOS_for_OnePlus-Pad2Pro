# 官方内核与 Erhai 补丁集

`7.3.4-erhai-p18` 从 `v7.4-dev` 移植 PCIe 驱动修复 `5121d76cb9dd`。
p17 的设备树改成了五字段映射，Linux 7.3.4 的 Qualcomm PCIe 驱动仍按四字段步长读取。
WCN7860 的 PCIe Requester ID 因而没有正确写入硬件 BDF-to-SID 表，启动等待到约 91 秒，
MHI 固件加载返回 `-5`，Wi-Fi 探测返回 `-110`。参考分支 `76ecaed9576c` 记录了同样的故障。
实机回滚 p15 后，`ath12k_wifi7_pci` 恢复绑定，Wi-Fi SSH 可用，系统启动时间为 13.1 秒。
p18 的驱动按 IOMMU 提供方的 `#iommu-cells` 计算表项步长，并兼容原四字段设备树。
严格重放、ARM64 交叉编译和设备回归检查通过。用实编 DTB 和模拟寄存器运行两个版本的
驱动函数，复现了 p17 遗漏 `0x100`，并验证 p18 对新旧 DTB 均写入 `0x100 → 0x1401`。
2026-11-19 完成平板原生系统构建和 kShimC 发布。经一级菜单手动进入 p18 后，
WCN7860 在内核启动后约 1.38 秒报告固件版本，Wi-Fi SSH 可用，经 `wlp1s0` 到网关
的 5 次 ping 全部成功。`systemd-analyze` 报告启动用时 18.0 秒。MHI 超时、PCIe
IOMMU 映射告警和视频节点等待日志均未出现，SCMI 正常注册。启动后 251 秒检查时，
`ufcs_sm` 处于空闲状态，内核日志无 error 及以上记录。系统 profile 已设为 p18，
kShimC 保留 p15 为 `previous`。本次未复测休眠恢复。

`7.3.4-erhai-p17` 候选处理 p15 启动和休眠日志。UFCS 的空闲等待使用 `TASK_IDLE`，
协议运行中的阻塞检测仍然生效。电池管理驱动在 ADSP 就绪前允许 uevent 省略尚无数据的
属性，就绪后重发状态。CAMSS 正确处理 PHY 延迟探测，并声明 TPG 实体类型。
PCIe 设备树显式指定 SMMU 流掩码 `0`，保留原有流 ID。LPASS 寄存器排序移植自
`246c785491bb`。FastRPC 在关联保留池前设置已有的 32 位一致性 DMA 掩码。
NT36536 将正常运行信息和面板关闭所取消的恢复记为信息日志，硬件操作失败仍报错。
CPS8601 在耗尽尝试时报告失败，启动时偶发的 I²C `-ENXIO` 仍待定位。
严格重放、ARM64 交叉编译、设备回归检查、112 项项目测试、平板原生系统构建和
kShimC 暂存发布均通过。实机启动发现上述 Wi-Fi 回归，已回滚。

对照了 Linux `v7.4-dev` 本地及远端分支。p15 同一次休眠记录了 USB HS-PHY、PCIe L2
和 Wi-Fi hwmon 警告，系统完成一次 s2idle 并恢复 SSH。需要独立复现并区分空闲、
USB 外设、接电与 Wi-Fi 唤醒条件。CPS8601 在 p14 能读取芯片并进入扫描，在 p15
观察到 hboost ACK 后无 I²C 应答。现有日志无法确认线圈电源实际输出或 MCU 启动状态。
全球 Wi-Fi 规则 `00` 被固件拒绝，设备使用自管理规则，仍需按实际部署地区核对。
ITS 表尺寸回退、PCIe 窗口／PCIe 与 GPU 电源告警、CoreSight 延迟探测和 ALSA 控件名截断
暂缓。控件名与现有 UCM 配置匹配，电源与窗口修改需要板级依据。

`7.3.4-erhai-p15` 候选修正 WCD MBHC 默认按键阈值的单位，驱动现在以 mV 使用
`500 mV`。LPASS VA 在未配置可选采样率时使用默认分频。两处驱动在已提供的
属性无法读取时保留警告。严格重放、ARM64 交叉编译、设备回归检查、平板原生系统构建
和 kShimC 暂存发布通过。2026-11-19 实机启动 p15，两条属性日志均消失，两个驱动已绑定，
ALSA 注册两个播放 PCM 和一个采集 PCM。耳机按键和麦克风拾音待实测。

`7.3.4-erhai-p14` 候选将 OPD2413 的 CCI0 运行时自动休眠延迟设为 `0 ms`。
p13 的 I²C 跟踪把超时定位到 CN3927 对焦器恢复供电后的第一笔初始化写入。
平板上，默认延迟下 5 次打开中有 4 次超时，强制 CCI 保持活动时 5 次均超时。
临时将延迟设为 `0 ms` 后，5 次快速打开均成功。严格重放、ARM64 交叉编译、
设备回归检查、平板原生系统构建和 kShimC 暂存发布通过。
2026-11-19 实机普通重启进入 p14，确认 CCI0 延迟为 `0 ms`。
对焦器以 30、90、240、1200 ms 间隔各开关 6 次，全部成功。后摄以 640×480 完成
3 轮采集，每轮 32 帧。启动及复测期间均未出现 CCI 队列超时。

`7.3.4-erhai-p13` 候选为 CCI0 指定原厂使用的 37.5 MHz 核心时钟，与当前驱动的
400 kHz 总线时序表匹配。实机 p13 启动仍能复现 CCI 超时。
CPS8601 编程寄存器表使用独立名称，避免两个 regmap 的 debugfs 目录重名。
严格重放、ARM64 交叉编译、设备回归检查、平板原生系统构建和 kShimC 暂存发布通过。

`7.3.4-erhai-p12` 候选从 `v7.4-dev` 移植 DSI PHY 引用计数修复
（`04181c69d563`），由 DSI 清理路径统一释放引用，并通过延迟探测机制记录 PHY 尚未就绪。
驱动核心将已完成探测的消费者跳过 `SYNC_STATE_ONLY` 链接的情况单独处理。
严格重放、ARM64 交叉编译、设备回归检查、平板原生系统构建及 kShimC 暂存发布通过。
实机验收需核对启动日志、DSI 初始化以及 Type-C 端口到 USB、组合 PHY 和 WCD939x USBSS 的链接。

`7.3.4-erhai-p11` 候选将 Erhai 显示控制器的 SMMU 上下文和页表初始化提前到域分配阶段。
IOMMU 核心可以在附加显示设备前建立启动帧缓冲区映射，消除 p10 附加后重试留下的空窗。
该调整仅用于声明了帧缓冲区的 OPD2413 显示控制器。严格重放、ARM64 交叉编译、
设备回归检查、平板原生系统构建及 kShimC 暂存发布通过。
2026-11-19 实机 p11 普通重启未见启动帧缓冲区 IOMMU 映射警告或 `SID=0x800` 转换故障。

`7.3.4-erhai-p10` 候选修复启动显示接管。Erhai 设备树保留原厂启动帧缓冲区，
并为 MDSS 建立该区域的 IOMMU 恒等映射。KTZ8868 仅在设备树声明外部偏压供电时请求对应
regulator，主背光 I²C 总线在设备树中显式指定 100 kHz。第 38 个补丁以摘要固定，
来源记录在 `provenance/boot-display-p10.json`。严格重放、ARM64 内核交叉编译、设备回归检查、
平板原生系统构建及 kShimC 暂存发布通过。

2026-11-19 平板从 p9 普通重启进入 p10。启动日志中 MDSS `SID=0x800` 转换故障
由 10 条降至 0 条，KTZ8868 dummy regulator 警告由 4 条降至 0 条，
`980000.i2c` 默认频率提示由 1 条降至 0 条。DSI 已连接并启用，背光和正负偏压正常注册。
仍有一条 IOMMU 初始化警告。ARM SMMU 在设备附加时才创建页表，因此附加前的第一次
映射尝试失败，IOMMU 核心在附加后重试。实机可见 `0xfc800000–0xff2fffff` 的
`direct` 保留区，显示驱动完成初始化。冷启动待验收。

`7.3.4-erhai-p9` 增加 PM8550 双 LED 和板载电池的 `charge_behaviour`。
内核沿用既有充电仲裁处理暂停、限充和快充退出。补丁集含 37 个补丁，严格重放和
完整系统构建通过。桌面设置见 [参考项目功能对照](MAINLINE-COMPARISON.md)。

`7.3.4-erhai-p8` 增加 CPS8601 磁吸笔蓝牙地址识别和 USB 光驱支持，共 35 个补丁。
地址仅供 root 读取，NixOS 的蓝牙服务据此连接当前吸附的笔。
见 [参考项目功能对照](MAINLINE-COMPARISON.md)。

2026-11-17：`7.3.4-erhai-p7` 增加 NT36536 默认笔扫描，原样移植上游
`b6fa42deb718`，共 33 个补丁；坐标／压感上报沿用已有实现。严格重放、
完整系统构建及 11 月 18 日重启后的笔输入分项验收通过，详见
[手写笔说明](PEN.md) 和 `pen-scan-p7-*.json`。
扫描开启与真实笔事件分别验收，不将设备注册视作书写通过。

2026-11-16：集成 `7.3.4-erhai-p6` 充电支持，保留 7.3 系列及现有 VDDIO 修复，
移植参考项目 0.10.2 的有线快充与接电唤醒实现；范围和验收状态见
[充电说明](CHARGING.md)。p6 已通过完整交叉内核／原生用户空间构建及 VCBAOBCH 的分项实测，
范围见 `charging-p6-device-acceptance.json`；下方 p5 实机记录作为历史验收保留。

2026-11-14 已完成迁移，日常内核为 nixpkgs 官方 Linux **7.3.4** 加独立设备补丁集，
标识 `7.3.4-erhai-p5`，共 23 个补丁。完整交叉与平板 ARM64 原生系统均已构建并校验。
原生冷启动、默认 current 普通重启、显示／触控／GPU／扬声器／Wi-Fi／蓝牙／充电和
RTC 休眠恢复通过；8 核在线、taint=0。2 GiB 并发 THP 四轮分配与读回通过，累计写入 8 GiB。

平板 `/etc/nixos` 已安装对应声明式配置，标准
`nixos-rebuild switch --flake /etc/nixos#pad2pro` 及再次激活通过。
原账户的 UID/GID、密码、家目录及所有者、附属组和 subuid/subgid 均保留，重启后可登录。
系统不声明普通账户，不绑定个人用户名。安装备份位于
`/var/lib/erhai-patchset/20261114-130657-final-install/`。

`current` 指向最新发布的系统代际，`previous` 指向前一代；保留数量由 kShimC 清理配置管理。
历史旧内核只作故障恢复，不新增适配。按用户选择，`/boot` 默认以 `rw,noatime` 挂载，
发布／清理工具保留原有挂载模式；两个入口的完整载荷与 GC roots 已核验。

## 构建关系

独立项目为 `linux-sm8750-erhai-patchset`，维护来源为官方 stable 基线上的 Git 分支
`patchset-7.3`。补丁与硬件配置由提交导出为 series、patches 和 manifest；本项目的
`inputs/kernel-patchset` 只能由同步工具生成。安装导出包含 `inputs/` 的发布快照及随 Git 提供的通用 OEM
固件归档，平板构建不需要电脑上的旧 fork 或开发仓库路径。

`packages/kernel.nix` 复用 nixpkgs `linux_7_3`。硬件模块通过 `boot.kernelPatches` 和
`structuredExtraConfig` 追加设备补丁与配置；先对正式源码打补丁，再生成最终 `.config`。
保留 defconfig、硬件片段和本项目 `packages/nixos.config` 的配置语义，最终启用／禁用
请求必须通过检查。DTB、模块、initrd 与 Bootspec 都引用最终 `config.boot.kernelPackages.kernel`。
CPS8601 修复已进入补丁集，不再注入重复的模块覆盖路径。

`pad2pro` 在平板原生构建内核；`pad2pro-build` 在电脑交叉编译内核，ARM 用户空间步骤
需要 ARM builder 或仿真。两者统一使用当前 nixpkgs 工具链，不保留旧编译器或历史闭包门禁。
设备补丁以 `--fuzz=0` 独立重放，编译源码逐文件核对重放结果；失败不得跳过。

## 更新与验证

在平板更新同系列正式版及工具链：

```sh
cd /etc/nixos
run0 nix flake update nixpkgs
run0 nixos-rebuild switch --flake /etc/nixos#pad2pro
```

升级前先完成补丁重放、配置、完整系统构建和候选实机验收，再提升默认。
需要修复补丁时，在独立项目修改 Git 提交并导出／验证，然后同步：

```sh
python3 tools/vendor-kernel-patchset.py /absolute/path/linux-sm8750-erhai-patchset
nix build .#checks.x86_64-linux.patchset-replay .#checks.x86_64-linux.device-regression
nix build .#checks.x86_64-linux.wifi-firmware .#checks.x86_64-linux.cps8601-firmware
nix build .#checks.x86_64-linux.boot-publication
nix build .#nixosConfigurations.pad2pro-build.config.system.build.toplevel -L
```

已实际完成 7.3.3 → 7.3.4 前移：删除上游已合入的修改，处理 stable 语义变化后重放、
构建并实机验收。下一系列先移植补丁，再修改包选择及 manifest；禁止改选较旧内核绕过失败。

## 验收与修复记录

- 正式源码重放与来源：`provenance/replay-7.3.4-p5.json`、`forward-7.3.4.json`。
- 完整原生系统、模块、BTF、最终 DTB／initrd 与固件：`full-native-system-p5-validation.json`。
- 原生设备验收与日常安装／重复激活／重启：`native-p5-device-acceptance.json`、`daily-p5-installation.json`。
- 面板首次上屏重启：VDDIO 固定为 1.896 V，见 `panel-vddio-diagnosis.json`。
  Android 原厂消费端请求、初始化值和亮屏驱动报告均为 1.900 V；1.896 V 是当前主线
  8 mV 模型的下方相邻档位，非原厂精确电压。对照和因果边界见 `android-factory-vddio-reference.md`。
  7.3 与参考 `v7.4-dev` 的实现比较、启动读回取整路径及维护建议见
  [XN242 VDDIO 分析](DISPLAY-VDDIO.md)。
- 蓝牙无法开启：修复 UART 关闭路径重复禁用 IRQ，见 `uart-irq-balance-diagnosis.json`。
- 内存负载中止：ADSP 的 12 MiB 堆改为专用 no-map 保留区，见 `adsp-heap-native-fault.json`。
  内核安装阶段必检实际 DTB，实机 memblock 已确认不与 System RAM 重叠。

以上 provenance 文件位于独立补丁项目及本项目 `inputs/kernel-patchset`。
历史闭包、哈希及失败尝试用于追溯，不作为以后固定工具链或旧构建产物的门禁。
