# GNOME 桌面

`hosts/pad2pro/default.nix` 导入 `modules/gnome.nix`，提供 GNOME Wayland、GDM
图形登录、文件管理器、终端、设置、Firefox、PipeWire、中文字体和 IBus 拼音。
使用自己创建的账户及密码登录；系统不预置普通用户名，也不设置固定账户自动登录。
桌面默认值通过系统级 dconf profile 发布，输入法、字体和音频用户服务对所有用户生效。
Fish 使用 `users.defaultUserShell` 配置全局默认值，账户由 GNOME 用户管理或标准工具管理。
3392×2400 内屏默认使用 200% 字体/界面缩放；可在 GNOME 显示设置中调整。
屏幕键盘由 GNOME 根据触屏自动启用，也可在无障碍设置中手动打开。

## 显示精度与 HDR

当前配置 `pad2pro` / `pad2pro-hdr` 默认使用 10bit 等效 HDR，保留 12bit 等效
精度，可在 HDR 开启时用 `pad2pro-display 10` / `pad2pro-display 12` 切换。
精度切换由系统脚本提供，不再创建模式切换的应用菜单或桌面快捷方式。
按内容调节背光和白位补偿已通过实机会话检查；完整校准状态见显示文档。
XR30 扫描及原厂 8-bpc RGB888 / DSC 链路不变；这些 DPU 显示修复现已纳入独立设备补丁集，日常内核见 [补丁集维护](KERNEL-PATCHSET.md)。
HDR 驱动、10bit/12bit 控制、Chromium 功能开关及视频默认值均为系统配置，
不依赖账户名、UID 或旧账户家目录。每个用户仍可在显示设置中独立选择是否开启 HDR。
新账户默认用 Chromium 打开网页、用标准 mpv 应用入口打开常见视频。
mpv 应用启动时按当前会话的显示状态选择原生 PQ 输出或 HDR→SDR 色调映射，避免重复
色调映射削弱高光。已有用户自行选择的默认应用仍优先于系统默认值。

所有账户可通过命令 `pad2pro-hdr-check` 运行高光诊断；诊断工具不占用应用菜单。
它从只读系统包加载同一套画布与正确标注 BT.2020/PQ 的 VP9 视频，不需要复制
旧账户的测试文件、播放器设置或网站数据。五块输入依次为 100/203/400/600/1000 nit；
数字是内容编码值，并非已测得的面板亮度。
TestUFO 请选 WebGL + Rec.2100 PQ；其 Canvas 2D 默认 headroom 为 0，会将
`drawImage` 的 HDR 高光映射回 SDR，这不是账户的 HDR 开关失效。

需要显式使用原生配置时，仍可运行 `pad2pro-native-hdr-player`，通过 16-bit
Wayland 表面保留高精度输入。没有 PQ 色彩标签的 PPM/FFV1 诊断内容不能靠
文件名推断为 HDR，应修复源文件的元数据；共享测试视频在打包时校验色彩标签。
原 `pad2pro-hdr-player` 用于将 HDR 内容映射为 SDR；`pad2pro-hdr10` 与默认配置
相同，`pad2pro-hdr-frc` 提供默认 12bit 的构建。测试步骤和硬件限制见
[显示精度与 HDR](DISPLAY-COLOR.md)。

## 软件版本与更新

桌面和系统用户空间跟随 `nixos-unstable`，`flake.lock` 记录本次可重现的依赖快照：

| 软件 | 本次版本 |
| --- | --- |
| NixOS | 26.11pre，nixpkgs `d4f25a3e5620`（2026-11-11） |
| GNOME Shell / Mutter | 51.0 |
| Mesa | 26.3.0，加 Adreno 830 补丁 |
| Firefox | 160.0 |
| 设备内核 | 官方 Linux 7.3.4 + Erhai p5，原生构建及实机验收通过 |

软件来自本次安装时最新的 NixOS unstable channel，而非每个上游项目的开发分支。
Mutter 和 Mesa 均不设置具体版本断言，更新 `nixpkgs` 后直接尝试应用现有补丁。
版本号变化本身不会阻止更新；补丁应用或编译不兼容时，再修复相应补丁。
`system.stateVersion` 仍为 `26.05`，该选项控制持久数据兼容性，不限制软件版本。
未开启无人值守升级；后续由管理员显式更新：

```sh
cd /etc/nixos
run0 nix flake update nixpkgs
run0 nixos-rebuild switch --flake /etc/nixos#pad2pro
```

内核、模块、模块聚合和用户空间统一使用更新后的当前 nixpkgs 工具链。
设备补丁在正式 `linux_7_3` 源码上重放；CPS8601 修复已进入补丁集。
历史闭包与实机记录只作追溯，不阻止工具链更新。同系列更新需通过补丁重放、
完整构建和实机验收；跨系列先移植补丁，不选择较旧内核绕过失败。

## GNOME 充电保护（2026-11-12）

当前内核已提供标准 `charge_control_start_threshold` 和
`charge_control_end_threshold`。UPower 1.91.5 的通用限充 hwdb 项要求 DMI
标识，这款使用设备树的 ARM 平板没有该标识，因此此前报告
`ChargeThresholdSupported=false`，GNOME 隐藏了充电模式选项。

`modules/gnome.nix` 增加 udev 规则，只匹配 `qcom-battmgr-bat`、
`Erhai_TABLET_*` 电池型号和两个已有的阈值属性，设置
`CHARGE_LIMIT=75,80`。UPower 现在报告支持两种阈值，GNOME“设置 → 电源”
可以显示“充满电量 / 保护电池健康”。规则提供默认策略，不自动开启保护模式；
GNOME 调用 UPower 的 `EnableChargeThreshold` 执行选择，UPower 保存开关状态。
原生界面不提供任意百分比输入。

实机以同一 D-Bus 方法验证：首次启用下发 75/80，当前电量 94%，约两秒后
电池电流由正转为接近零的负值，USB 仍在线；内核记录
`charging stopped at 94% (end threshold 80%)`。关闭保护后截止恢复为 100%，
内核记录恢复充电，随后读到正充电电流。运行中的 GNOME 设置进程通过默认
Polkit 权限检查；通过 SSH `runuser` 创建的非活动桌面进程不具有该权限，
无需也没有放宽 Polkit 规则。该次测试结束时保留关闭保护、允许充到 100% 的状态。

已知边界：UPower 关闭保护会写入起充 0 / 截止 100，驱动把起充 0
夹到最小允许值 50。截止 100 仍能正确取消限充，但 UPower 在后台重启时会
优先采用这个有效的起充读数，因此后续保护模式可能为 50/80，而不是默认的
75/80。该次修复设备识别，没有改动内核，也不宣称 75% 恢复点跨所有操作
始终固定。该兼容性问题应在共享内核后续修正；80% 截止与取消限充已验证。

限充由 Linux 驱动约每 30 秒检查电量后发送充电开关命令，不是把截止电量
固化进充电固件。挂起时工作队列可能冻结，尚未验证跨阈值的挂起限充、
75%/50% 自动恢复点的完整放电过程及断电冷启动后的状态恢复。
修复配置已经在线启用并持久发布，原内核、模块、设备树及 77 个固件文件不变；
构建、激活和原配置备份位于平板
`/var/lib/pad2pro-updates/gnome-charge-limit/`。

## Adreno 830 驱动

`packages/mesa-erhai.nix` 使用 nixpkgs 的同版 Mesa 源码和构建配方，应用参考项目
`4cc3570c…` 的六个原始补丁。`packages/mesa/upstream-source.json` 保留来源和摘要。
包括 revision-1 speedbin 识别、共享上下文/纹理并发、显式同步和 Turnip 修复。
通过 `hardware.graphics.package` 安装 Freedreno / Turnip，保留软件渲染回退。
无需为整个桌面设置 `LD_LIBRARY_PATH`，也不强制软件渲染。

后续 channel 更新会使用新版 Mesa 正常应用这些补丁；若无法应用或编译失败，
再移植补丁。来源清单记录补丁取得时的版本与摘要，不参与软件版本选择或限制。
构建成功后的运行行为仍可通过实机 GPU 检查核对。

## 电源和硬件边界

GNOME 会话和 GDM 仍默认关闭闲置自动挂起；7.3.4-erhai-p5 已通过 RTC 休眠／恢复验收，
普通屏幕锁定仍可使用。现有电源键由 GNOME 显示操作菜单。
内置扬声器与麦克风已接入 PipeWire，并经 GNOME 听音与输入电平检查。
采用保守功放增益，原厂 DSP 扬声器保护仍未实现；详见 [内置音频](AUDIO.md)。
蓝牙自动初始化状态见 [蓝牙适配](BLUETOOTH.md)；传感器自动旋转和摄像头仍需后续单独适配。

## 安装及回退

日常内核为已验收的原生 7.3.4-erhai-p5；`current` 跟随最新系统代际，`previous` 指向前一代；
启动分区默认读写挂载，具体维护方式见 [补丁集维护](KERNEL-PATCHSET.md)。
最新安装、账户数据库及 NixOS 账户状态备份位于
`/var/lib/erhai-patchset/20261114-130657-final-install/`。
此前桌面更新的历史记录仍位于 `/var/lib/pad2pro-updates/gnome/`。
