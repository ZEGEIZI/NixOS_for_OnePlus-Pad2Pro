# Pad 2 Pro：显示精度与 HDR

Mutter 打包不限制具体软件版本，跟随 `nixpkgs` 更新并正常应用显示补丁。
更新导致补丁无法应用或编译失败时，再移植补丁；构建成功后的行为变化仍需
实机检查。`flake.lock` 保留依赖快照以便复现，通过更新输入选择新版，
不再用版本号断言阻止升级。

本次目标是确认并改进显示链路，不把 XR30 帧缓冲、面板 FRC、10-bit DSI 传输和
原生 HDR 混为一谈。`pad2pro` 使用已验收的 color1 内核和带 HDR 补丁的
Mutter。`pad2pro-color` 保留标准 Mutter，供独立显示测试。

## 控制脚本与应用入口（2026-11-13）

HDR 精度选择使用 `pad2pro-display 10` / `pad2pro-display 12`，状态查询使用
`pad2pro-display status`；脚本源码为 `tools/display-precision.sh`。先在 GNOME
显示设置中开启 HDR，再选择精度。高光诊断使用 `pad2pro-hdr-check`。
不再为精度切换、诊断、SDR 映射或原生输出分别创建 `.desktop` 应用入口。

播放器只保留正常的 mpv 应用身份与 `mpv.desktop`，常见视频默认关联指向它；
内部启动脚本自动跟随当前会话 HDR 状态。显式播放配置仍保留为命令行工具，
`umpv` 的辅助应用入口也不再发布。所有账户共用同一套配置和脚本。
本次整理已发布为 `nixos-5616666963163da5e7d024d8ee9b3afb`，10bit/12bit 脚本及正常 mpv 入口均已验证。

## 终端 mpv 的 Wayland 输出（2026-11-15）

GNOME Console 的进程环境可能没有 `WAYLAND_DISPLAY`。此时普通 `mpv`
自动探测会跳过 Wayland，尝试直接 DRM/KMS 输出，因 GNOME 已持有 DRM master
而报 `Failed to acquire DRM master` / `Failed to set CRTC`，最终没有视频画面。

`modules/gnome.nix` 通过 `/etc/mpv/mpv.conf` 为所有用户设置 `vo=gpu-next`、
`gpu-api=opengl`、`gpu-context=wayland`。显式选择 Wayland 后可以使用默认会话
socket，无需提升播放器权限。已有用户配置和命令行参数仍可以覆盖这些默认值。
`--no-config` 会跳过系统配置，诊断时需显式传入以上三个参数。

实机在缺少 `WAYLAND_DISPLAY` 的环境中复现了自动探测失败；显式后端成功
解码并渲染 3840×2160 HEVC Main10（`yuv420p10`），渲染器为 Adreno 830。
保留用户的底部视频留白及字幕参数，未执行持续播放性能或 HDR 高光验收。
HDR 自动选择仍通过前述 `pad2pro-video-player` 入口完成。

## 所有账户共用的 HDR 入口（2026-11-13）

HDR 驱动、Mutter 补丁、10bit/12bit 控制和 Chromium API 开关由系统发布，
不按账户名、UID 或家目录绑定。当前新账户已在空白浏览器及播放器配置下通过
10bit、12bit 两组测试：参考画面背光 1053，真实高光 2047，移除后恢复 1053；
参考白保持约 26.08 nit。浏览器均报告 HDR/30-bit，三种 PQ Canvas 保留五个
不同输入级，带 BT.2020/PQ 标签的 VP9 视频正常解码。用户已目视确认共享页面
的三行画布和视频均有高光层次。

高光测试使用命令 `pad2pro-hdr-check`，不创建功能型应用入口；测试页面、参考白、
高光及五级灰阶视频均置于只读系统包，所有账户使用同一份资源。
`packages/hdr-test-patterns.nix` 生成 10-bit 限幅 YUV、编码为无损 VP9，并校验
BT.2020 原色、ST2084/PQ、矩阵和像素格式。此视频检查高光输出，不用于证明
面板拥有原生 12-bit 精度。原始 PPM/未标注色彩的 FFV1 不再作为账户初始化测试片。

常见视频 MIME 的系统默认入口为标准 `mpv.desktop`。它使用内部启动脚本
`pad2pro-video-player` 查询当前用户会话的 HDR 状态：开启时使用原生
PQ 配置，关闭或会话接口不可用时使用现有 HDR→SDR 配置。网页默认使用 Chromium；
已有用户自行选择的默认应用仍保留。用户仍可在 GNOME 设置中独立选择 HDR 开关。

本次排查也复现了两个容易误判的问题：TestUFO 的 Canvas 2D 默认
`globalHDRHeadroom=0`，将 `drawImage` 高光映射回 SDR，应选 WebGL/Rec.2100 PQ；
没有 PQ 标签的旧 FFV1 诊断片会被正常识别为 BT.709/sRGB。补充正确输入标签后，
当前账户的原生播放器可把相同高光输出到完整范围。普通 mpv 的自动目标色调映射
还会与合成器重复压缩高光，新的默认入口避免这一步重复映射。
共享入口已持久发布为 `nixos-fc4360d2abc095fc0d7732e2bf4dc064`，当前会话已生效。
记录见 `artifacts/nixos-pad2pro-hdr-all-users/`。数字亮度仍为模型估计，未做光学校准。

## 默认 10bit HDR 与按内容调节背光（2026-11-11，实机会话验证通过）

新会话已加载该实现并通过实机检查：10bit/12bit HDR 可即时切换，普通用户与
root 的 `power-top.sh` 均正确识别；HDR → SDR → HDR 回到默认 10bit。
原 SDR 背光 1187，在只有参考白的 HDR 画面中为 1207；加入 32×32 的 1000 nit
内容高光后升至 2042，移除后回到 1207，两种精度均通过。参考白设定全程不变，
用户目视反馈大白块“基本稳定”。HDR 滑块值 10/50 对应硬件背光 969/1499，
不再固定满背光；退出 HDR 恢复原 SDR 的 1187。测试过程接有 USB 供电，未将
这些采样作为新的电池功耗对照。原始记录在 `artifacts/nixos-pad2pro-adaptive-hdr/`。

`pad2pro` / `pad2pro-hdr` / `pad2pro-hdr10` 默认采用 SDR + 8+2-bit，开启 HDR
后仍为 8+2-bit。两种精度编译在同一个 Mutter 中，无需更换系统或注销即可选择：

```sh
pad2pro-display 12       # 已开启 HDR、刷新率至少 100 Hz 时选择 8+4-bit
pad2pro-display 10       # 回到 8+2-bit HDR
pad2pro-display status   # 读取运行合成器的精度、背光和亮度估计
```

精度切换保留为 `pad2pro-display` 脚本，不再创建 10bit/12bit 的独立应用入口。
关闭 HDR 恢复 10bit SDR，下次开启 HDR 默认 10bit。`pad2pro-hdr-frc` 是明确要求默认
12bit 的独立构建配置。物理链路仍为 8 bpc；这些名称描述输出抖动的等效精度。

背光策略仅适用于匹配的 OPD2413/XN242 内屏：

- GNOME 滑块决定 SDR 参考白。首次进入 HDR 时从此前硬件背光估计白位，
  不直接设满背光；退出 HDR 时恢复先前 SDR 硬件设定。
- 在已经绘制的画面上，以最多 10 Hz 做 GPU 4×4 分级最大值归约，检查全部像素。
  统计在背光补偿和最终 FRC 之前，避免反馈环或抖动干扰。单像素高光不会因
  缩略采样漏掉。静止画面只补做最后一次采样，10bit 模式不持续强制重绘。
- 只需 SDR 白位时，以参考白加 4% 余量为背光需求；出现实际高光时提高背光，
  最高至已有的 2047 档。保留高光约一秒，再缓慢回落；上升和下降有不同速度。
- 依据实际背光读回值，对最终 Gamma 2.2 像素值补偿，保持模型中的 SDR
  参考白。硬件尚在上升时使用保留白位的临时高光肩部，避免生硬裁剪。
- Wayland MaxCLL 参与内容峰值映射；MaxFALL 校验与 MaxCLL 的关系，但不把
  整段视频的最大平均亮度当成当前帧需求。兼容 libplacebo 的零值“未知”标记。
  10000 nit 编码范围不直接当作实际片源峰值：采用 1000 nit 名义拐点并保留
  向上的平滑尾部，避免缺失元数据时裁掉更高亮度内容。
- Tone Mapping 锚定所选 SDR 白位，将已声明内容峰值映射到显示器能力，按 RGB
  共同缩放保留色相；提高背光不会修改应用的白位。Wayland 持续公布完整显示
  能力，瞬时背光补偿在最后一级完成，避免随背光向应用反复切换色彩描述。

561.5 nit 峰值来自厂商参考；KTZ8868 的背光码值到亮度目前使用指数电流曲线
估计，尚未经光度计校准。`GetState` 明确返回 `luminance-calibrated=false`。
数字测试中的白位稳定不等于已经测得光学白位稳定。背光与扫描输出没有原子
提交接口，渐变控制只能减少两者更新时差；LCD 的黑位也会随全局背光变化。

会话 D-Bus 接口为 `org.gnome.Mutter.Xn242`，对象路径
`/org/gnome/Mutter/Xn242`，提供 `SetPrecision(u)` 和 `GetState() → a{sv}`。
`power-top.sh` 优先读取与当前合成器 PID 一致的实际精度，普通用户也可识别
8+2/8+4；DRM 扫描格式字段仍可能需要 root。旧合成器保留原检测路径。

## 先前 HDR 与 8+4-bit 联合候选（2026-11-11）

按同时支持 HDR 与 12-bit 精度的目标，`pad2pro` / `pad2pro-hdr` /
`pad2pro-hdr-frc` 当时启用同一套 HDR + 8+4-bit 输出。`pad2pro-hdr10` 明确关闭
FRC，保留原 HDR 合成路径用于对照。设备内核、模块和 8-bpc DSI/DSC 不变。
本轮已在新登录会话中确认补丁加载：HDR 开启，实际合成缓冲为
`RGBA_16161616_PRE`，扫描输出为 XR30，两路 DPU 抖动均启用，接口 underrun 为 0。
最近 30 个约一秒采样的重绘帧率为 116.60～120.03 FPS，中位数 119.95 FPS。
HDR → SDR → HDR 临时切换通过，返回 HDR 后恢复 UNORM16/FRC 输出。
用户已确认五块 HDR 灰阶均能区分，渐变稳定，没有明显闪烁或颗粒。
这些结果覆盖本次软件路径及目视观察；绝对亮度、光学有效位数和持续功耗未测量。

### 临时 10bit + HDR 功耗对照（2026-11-11）

本次测试临时移除 `/etc/mutter/xn242-output-frc` 开关，并通过临时 SDR → HDR
切换重建所有输出 view，不需要注销、重启或替换合成器。实机亮屏确认
`HDR=ON Color=8+2-bit Hz=120.00 Scanout=XR30`，HDR 背光为 2047。
默认 Nix 配置仍保留 HDR + 8+4-bit；本次测试关闭了额外 FRC 和其 UNORM16
合成路径。对照恢复后应保持相同内容和背光，等待切换波动结束，再清零均值。

以下命令仅用于先前的临时实现；新合成器请使用上面的 `pad2pro-display 12`：

```sh
ssh root@192.168.2.206 'bash /run/temporary-hdr-precision.sh 12'
```

临时脚本的本机副本为 `.work/temporary-hdr-precision.sh`；恢复时重新建立原开关
并重建输出 view。`power-top.sh` 仅在开关缺失且存在 root 确认记录时识别这个
临时关闭状态：记录绑定原合成器 PID、进程启动时刻，并记录关闭完成时的单调时钟
tick。原进程和此后启动的新合成器均可确认禁用 FRC；早于关闭时刻的其他进程
不能沿用该确认。这样既避免使用旧 FRC 日志，也能在合成器重启后继续识别。
记录位于 `/run/pad2pro-precision-test/frc-disabled`，随重启失效。已运行的旧版
功耗工具需要退出重开，才能使用新增检测。
临时 10bit 模式的 XR30 扫描格式仍需要 root 读取 DRM debugfs；普通用户在格式
不可读时显示 `Color=N/A`，请通过 root SSH 运行完整检测。

先前 FRC 候选的 Gamma 编码中间缓冲使用 FP16。它在亮部只有约 11 位有效
精度，会将 4081 个目标值合并为约 3065 个值。候选现改用 UNORM16 中间缓冲，
不支持时尝试 FP32；不回退到会丢失细分值的 FP16。最终 FRC 将相邻 8-bit 码值
间隔分成 16 份，产生 4081 个端点在内的平均码值，属于约 12-bit 等效抖动，
不是已经证实的原生 4096 级面板或 12-bpc 传输。

`tests/xn242_output_frc.c` 与 `tools/check-output-frc.py` 从实际补丁源码提取
FRC GLSL，在 GPU 上依次经过中间纹理和 RGB10_A2 输出，检查所有目标值、RGB
通道、每帧空间平均及 16 帧时间平均。Adreno 830 上 FP16 负对照产生 89136 个
不匹配，UNORM16 与 FP32 均为零。该结果不覆盖 DSC 重建或面板光学响应。

保留命令 `pad2pro-native-hdr-player`，向 Wayland
提交 AB48 / RGBA16 UNORM 表面，避免输入侧 RGB10_A2 或 PQ FP16 降低精度。
播放器保留 PQ/BT.2020，输出范围为 PQ 的 10000 nit 编码范围，由 Mutter 处理
面板高光压缩和最终抖动。先开启 GNOME HDR，再运行：

```sh
pad2pro-native-hdr-player /path/to/hdr-video.mkv
```

原来的 `pad2pro-hdr-player` 继续用于将 HDR 内容映射到 SDR。
`tools/make-hdr12-pattern.py` 生成 16-bit RGB 测试图：最上方五个 PQ 亮度块，
下方三排暗、中、亮渐变，每排从左至右分别为 8、10、12-bit PQ 输入精度。
对于没有正确色彩元数据的 FFV1 诊断片，显式使用
`--vf=format=primaries=bt.2020:gamma=pq`；不要依赖文件名推断 PQ。

本次使用的真正 12-bit HEVC / BT.2020 / PQ 单帧文件、带 cICP 标记的 16-bit
PNG 原图、生成脚本和说明已保存在平板 `~/图片/HDR与12bit测试图/`。
当时的账户内测试入口曾支持全屏打开；当前统一改用 `pad2pro-hdr-check` 命令。
PNG 解码后的 RGB 样本摘要与原始参考图完全一致。
电脑上的归档及实机记录在 `artifacts/nixos-pad2pro-hdr12-v2/`。

## 原厂与当前 Linux 链路

一加[同系列 Pad 3 的官方规格](https://www.oneplus.com/ca_en/oneplus-pad-3/specs)将 12-bit
标为 **8-bit 硬件 + 4-bit FRC**。本机链路位深以 Pad 2 Pro 原厂 DTB 和实机读取为准。

本地原厂 DTB 来自 Armada 的 `devices/oneplus-pad2pro/inputs/local/stock-device-trees/`
`live-devicetree.dtb`，SHA-256 为
`ee559b708c71204421623e5a497e5a6ae15c5aa17d4b2cac0fdb90fa7a3c2d68`。
实际选择的 `qcom,mdss_dsi_panel_XN242_P_D_A0024_vid` 使用：

| 项目 | 原厂值 | Linux（color1） |
| --- | --- | --- |
| DSI RGB 位数 | 24 | RGB888 |
| DSC 版本 | 1.2 | 1.2 |
| DSC 每分量位数 | 8 | 8 |
| DSC 每像素压缩位数 | 8 | 8 |
| 普通背光最大值 | 2047 | 2047 |
| HDR 面板标志 / 原色 | 该节点没有 | 没有可验证的 PQ/BT.2020 输出声明 |
| 合成 / 扫描缓冲 | 独立于链路 | 联合路径使用 UNORM16 合成、XR30 扫描；原生播放器提交 AB48 / RGBA16 |

原厂 DTB 同时包含许多其他机型面板，不能套用其中其他节点的 HDR 属性。
OnePlus 原厂驱动 `dsi_panel_parse_hdr_config()` 也明确以 `hdr-enabled` 为入口，
只在开启后读取 HDR 原色和亮度；单独存在亮度字段不表示启用了 HDR。
源码固定在 `cc463675855afb8702a263f415330a240f5cd919`：
https://github.com/OnePlusOSS/android_kernel_modules_and_devicetree_oneplus_sm8750/blob/cc463675855afb8702a263f415330a240f5cd919/vendor/qcom/opensource/display-drivers/msm/dsi/dsi_panel.c#L3804

峰值/平均亮度字段存在，但在确认其单位、作用路径与实际面板曲线前不作为校准数据。
原厂完整 DTB 的反编译文本含设备专属启动信息，不纳入公开资料。

## 为什么不直接套用 0142

Armada `0142-drm-msm-elden-dsc12-10bpc.patch` 针对 `lenovo,elden` 的 CSOT C-PHY
面板及其 10-bpc DSC 初始化。本机 XN242 面板的原厂 PPS 和链路均为 8-bpc。
共享内核已经包含该补丁的一部分通用 DSC 计算；仅改 `.bpc=10` 或 RGB101010
既不能添加 HDR 转换，也不能证明面板能接收相应格式。

## 本次可实现的改进

共享内核加入 `qcom,dpu-8bpc-dither`，为 XN242 启用 DPU 现有的静态有序抖动矩阵：
高精度合成的低位信息通过输出量化分布到相邻像素，减少直接截断产生的色阶。
沿用 Armada `0049-drm-msm-dpu-panel-opt-in-8bpc-dither.patch` 的机制及作者归属，
采用硬件厂商属性名，避免共享内核依赖发行版命名。时间抖动保持关闭。
该功能不能等同于原厂的 8+4 FRC，也不增加真实亮度范围或原生 10-bit DSI。

本项目 `docs/history/kernel/patches/dpu-xn242-8bpc-dither.patch` 用于在冻结源码上复现候选。
`packages.x86_64-linux.color-kernel` 构建候选，`nixosConfigurations.pad2pro-color`
用于独立实机测试，版本后缀为 `color1`；原冻结闭包和配置保持可重现。

`pad2pro-hdr-player` 使用 mpv / libplacebo：16-bit 浮点中间缓冲，BT.2390 色调映射，
感知色域映射，优先使用已经实测的 RGB10_A2 Wayland 表面，并按 EGL 表面位深抖动，
将 HDR 视频映射为 sRGB / BT.709 SDR 内容。
需要显式 SDR 映射时运行：

```sh
pad2pro-hdr-player /path/to/video.mkv
```

这是 HDR 内容播放兼容，**不是原生 HDR 输出**。为避免当前平台的视频硬件解码兼容
问题，此配置采用软件解码；高分辨率视频性能需单独测试。100 nit 为 SDR 映射参考值，
不是测得的屏幕亮度，不会自动改变系统背光。

## 原厂校准与 GNOME HDR 候选

从本机 Android `odm_a` 只读提取到 XN242 专用 QDCM 配置和 PanelChaplin 的 RGB/XYZ
测量样本。`tools/inspect-xn242-color.py` 可以从原始文件重新生成摘要；原始厂商文件不入库。
`24924_d65_hdr` 的目标为 P3、Gamma 2.2、561.5 nit，原厂 LUMA 输出抖动的时间项关闭。
最大档的 ODF 样本给出约 595 nit 白、0.531 nit 黑和 2.193 的灰阶 Gamma 拟合。
这些是厂商文件中的测量/配置数据，不是本次 Linux 实机的光度计测量。

`pad2pro` 和别名 `pad2pro-hdr` 复用已启动验证的 color1 内核和带补丁的 Mutter 51.0。
Mutter 在匹配 OPD2413 内屏、DPU 抖动设备树和 2047 档背光时，为内屏提供 GNOME HDR 选项。通过 Wayland 接收 PQ 内容，在合成器中完成
线性光转换、原厂样本原色/白点矩阵、203 nit SDR 白位和高光压缩，再以 Gamma 2.2
和 10-bit 合成精度输出。内屏的 DRM 编码仍为 Default；无需伪造 EDID、强制 HDR
调试选项或给 DSI 发送 PQ 元数据。Mutter 在 HDR 下设定满背光，亮度滑块调节
SDR 参考白。退出 HDR 时恢复先前的硬件背光。
HDR 映射使用自行实现的单调高光压缩，未复用或宣称复现原厂私有 HDR LUT、动态算法和 HBM。
夜灯仍保持禁用。

候选已实机启动并开启 HDR。Mutter 报告 `color-mode=1`，GNOME 以每通道 10 bit 的
XR30 扫描输出，两路 DPU 抖动均已启用，DSI 链路为 8 bpc。10-bit 缓冲由合成器自动
选择。当前内屏驱动只提供一种链路位深，显示设置没有 10/12-bit 切换项。
用户已用原生播放器完成灰阶对照：关闭 HDR 时只能分辨两级，开启后五级均清楚
可分辨。这确认了该原生播放路径的亮度层次；绝对出光亮度、退回 SDR 后的背光
和息屏唤醒仍需单独检查。
验证时先手动选择 kShimC 的 `(current)` / `NixOS GNOME HDR v1`，登录 GNOME 后在
“设置 → 显示器”开启 HDR。确认 SDR 桌面正常，然后播放从左至右为
100、203、400、600、1000 nit 的 PQ 灰阶测试片：

```sh
pad2pro-hdr-player --target-colorspace-hint=yes --target-trc=pq \
  --target-prim=bt.2020 --target-peak=1000 --loop-file=inf \
  /var/lib/pad2pro-updates/native-hdr-v1/hdr10-steps.mkv
```

记录 HDR 开关、亮暗层次、退回 SDR 后的背光，以及息屏唤醒；如出现异常，从 kShimC
选 `(previous)` 返回已验证的 color1 桌面。主机读取验证只证明载荷和选择规则正确。

## 验证记录

- DPU 策略测试编译实际辅助函数，验证桥引用释放、6/8/10-bpc 策略、矩阵和时间抖动关闭。
- NixOS 23 项回归测试通过，包括启动发布及额外维护代际的保留。
- 当前实机 mpv 0.42.0 / libplacebo，Adreno 830 OpenGL，960×540 HEVC Main10 测试通过。
  解码帧确认 BT.2020 / SMPTE ST2084、1000 nit mastering 和 MaxCLL 元数据；日志含
  PQ 解码、色调映射与抖动 shader，正常播放结束。尚未验证 4K 解码性能。
- 候选 `color1` 内核、模块和 CPS8601 模块构建通过，配置仅 LOCALVERSION 与 wifi1 不同。
  DTB 包含输出抖动属性。候选已发布为 `nixos-1f97848ec95c5167717410f06b0c3c36`，
  前一代 `nixos-eaed743938f46375f680ff49021d1d1c` 是原内核加播放器的系统。
- color1 已实际启动并登录 GNOME Wayland，用户确认显示正常。亮屏时两个活动
  ping-pong 抖动块读回均为 `enable=1`、`bitdepth=0xaa`，即四个 8-bpc 量化通道；
  息屏时关闭，唤醒后恢复。内屏仍为 3392×2400@120、最大输出 8 bpc。
- Adreno 830 使用 RGB10_A2 EGL 配置播放 Main10，实际三个颜色通道为 10 bit，
  libplacebo 执行 10-bit 输出抖动。当前播放器仍可在 SDR 桌面完成 HDR 色调映射。
- `pad2pro-hdr` 候选为 `nixos-5e7103ffe05939a2a6e8b6e2bfb467ff`。实机测试期间，Linux 菜单
  默认选择 `(current)`。选择 `(previous)` 可返回已验证的 color1 代际 `nixos-1f97848ec95c5167717410f06b0c3c36`。
  为给测试代际腾出一个菜单位，仅隐藏旧 GNOME 初始代 `nixos-0522dfa2eed0159cbd45b6b5d6675dd2`，
  保留其载荷。未更新冻结的 wifi1 维护基线，也未刷写 Android 启动分区。

## XN242 8+4-bit 时空抖动试验

`pad2pro-hdr-frc` 启用 `hardware.oneplus-pad2pro.experimentalOutputFrc`。Mutter
在 XN242 内屏开启 HDR 且刷新率至少 100 Hz 时，用 UNORM16 缓冲合成，在最终色彩转换后
将每个 8-bit 码值间隔细分为 16 份。每个 4×4 像素块在一帧内使用全部 16 个阈值，
每个像素在 16 个相位内也会遍历全部阈值。最终选中的 8-bit 码值写入 XR30 通道的
高 8 位，沿用 RGB888/DSC 链路。

试验需要内屏每帧重绘并经过合成器。`pad2pro-hdr10` 保留原 HDR 输出用于对照。
应在相同亮度和刷新率下对比两版，检查灰阶过渡、颗粒感、闪烁和帧率。
像素读回只验证数字码值。面板的光学响应及与 ColorOS 的差异需要实机对比。

使用 `artifacts/nixos-pad2pro-frc12/frc-gray-pq.mkv`。每组上方是按 8-bit
码值取整的灰阶，下方是 16 等分的灰阶。测试片以 16-bit RGB 存储，播放器显式标注
BT.2020/PQ，并通过 RGBA16F Wayland 缓冲提交给 Mutter。

```sh
mpv --no-config --vo=gpu-next --gpu-context=wayland --gpu-api=opengl \
  --egl-output-format=rgba16 --fbo-format=rgba32f \
  --vf=format=primaries=bt.2020:gamma=pq --target-colorspace-hint=yes \
  --target-trc=pq --target-prim=bt.2020 --target-peak=562 --dither-depth=no \
  --fullscreen --keep-open=yes /path/to/frc-gray-pq.mkv
```

## Chromium 网页 HDR

### 当前修复：保留浏览器 HDR 与按内容背光（2026-11-13）

Chromium 保留原生 Wayland 色彩管理及 HDR Canvas API。此前通过
`--disable-features=WaylandWpColorManagerV1` 将浏览器限制为 SDR 的方案已撤回；
它能避免高背光，但同时失去了网页 HDR，不能满足两项要求。

Chromium 的四项 HDR API 使用同名 `base::Feature` 开关启用：
`--enable-features=CanvasHDR,CanvasToneMapping,CanvasGlobalHDRHeadroom,CSSVideoDynamicRangeMediaQueries`。
此前的 `--enable-blink-features` 是开发者覆盖接口，会触发“不受支持的命令行标记”
信息栏；现已改为 FeatureList 接口。浏览器原生无障碍界面的对照读回确认，旧参数
存在该警告，新参数没有；HDR Canvas、高光升降及 TestUFO WebGL/PQ 复查通过。
记录见 `artifacts/nixos-pad2pro-chromium-feature-flags/`。

`mutter-xn242-pq-preferred.patch` 仅对已经启用自适应 HDR 的 XN242 内屏，
在 HDR 模式下向 Wayland 客户端首选描述提供 PQ；实际面板输出继续采用原来的
Gamma 2.2。PQ 的 10000 nit 编码范围与约 561 nit 的目标显示峰值分别发送，
所选 SDR 参考白继续随 GNOME 亮度设定更新。SDR 模式仍公布原来的 SDR 描述。

Chromium 157 此前在原生 Gamma HDR 表面上将普通网页白色编码为 1，却声明
1000 nit 编码峰值和 203 nit 参考白，造成约 4.93 倍的白位偏差。改为 PQ 首选后，
浏览器通过明确的 PQ 编码传递 SDR 白色与 HDR 高光，合成器保留白位映射和
可见像素采样；普通白色不应再被当作 HDR 高光。

实机会话已加载修复：系统 HDR/10bit 与浏览器 HDR/30-bit 同时启用。普通白、
灰、黑网页背光均为 1467/2047；加入 32×32 的 1000 nit PQ 高光后为 1987，
移除后回到 1468。参考白全程约 91.11 nit，普通网页采样峰值约 92.79 nit。
TestUFO 的 WebGL/PQ 使用 16-bit 浮点通道和 extended HDR，最大 PQ 通道约
0.82764（约 2000 nit 内容输入）；实际显示时背光能升至 2047，关闭后回落。
SDR → HDR 切换时浏览器分别报告 SDR/24-bit 与 HDR/30-bit，模式跟随正常。
三种 PQ Canvas 的五级灰阶输入保持可区分，浏览器 VP9/PQ 视频正常解码。
修复已持久发布为 `nixos-13c5d9ee620f48388a58213c57996778`，无需再次注销。

本轮代码及实机诊断记录在 `artifacts/nixos-pad2pro-chromium-hdr-backlight/`。
背光码值和合成器估计值不代表已经做过光学校准；TestUFO 的 Canvas 2D 默认
headroom 限制仍由网页的 API 调用决定，网页 HDR 验收使用下述 WebGL 引擎。

### 历史：此前启用的网页 HDR 配置

此前 `pad2pro` 和 `pad2pro-hdr-frc` 的系统 Chromium 使用原生 Wayland，并启用
Chromium 157 所需的 HDR Canvas 和视频媒体查询功能。应用菜单和终端调用同一个系统包。
切换到新版系统后，需要退出已经运行的 Chromium 进程，再从应用菜单打开。
在 TestUFO 内选择 `HDR - Rec.2100 PQ` 和 **`WebGL`**，并保持 GNOME 的 HDR 开启。
当前 TestUFO 的 Canvas 2D 路径会将其 HDR 图像高光映射回 SDR，不用于此项验收。
TestUFO 的 PQ 选项描述网页内容。判断实际输出模式时，以 GNOME 的色彩模式与 Chromium
的 `dynamic-range` 媒体查询为准。XN242 切回 SDR 后使用 SDR 的默认参考白，防止
HDR 参考白的异步更新使 Chromium 误判还有高光余量。
- 验证材料见 `artifacts/nixos-pad2pro-color/` 和 `artifacts/nixos-pad2pro-native-hdr-v1/`。

### Chromium 157 亮度描述排查（2026-11-11）

用户已确认原生 PQ 灰阶正常，Chromium/TestUFO 的实际画面仍异常。单凭
`dynamic-range: high`、30-bit 色深或成功创建 PQ Canvas，不能判定浏览器画面正确。
实机协议记录显示，Mutter 的窗口首选描述为面板原色、Gamma 2.2、561 nit 峰值，
参考白会随 GNOME 的 SDR 亮度调整（先前采样为 203 nit，本轮基线为 142 nit）。
Chromium 返回浮点窗口，却一直声明 Gamma 2.2、1000 nit 峰值和 203 nit 参考白。
Chromium 上游也修复过主平面峰值描述问题：
[变更 8641498](https://chromium-review.googlesource.com/c/chromium/src/+/8641498)。
该协议差异仍需通过候选会话的实际输出验证，不能把上游问题直接当作全部故障的证明。

随后用户确认，同屏测试 A/B/C/D 四行都可看到五级，四种路径没有明显区别。
三种 Canvas 的数据读回也分别保留五个不同的 PQ 值，浏览器 VP9/PQ 视频正常解码。
因此撤回“TestUFO 观感异常意味着 Chromium HDR 整体失效”的判断。当时未部署
新的 Mutter；PQ 首选描述原型只留在 `.work/hdr-pq-preferred/`，未进入当时默认构建。
2026-11-13 的背光修复已重新移植并实测启用 PQ 首选描述，见上面的当前修复。
上述元数据差异仍属于独立的准确性问题，不等于本轮已经证明它造成了目视故障。

后来用户确认：TestUFO 切换成 WebGL 可看到 HDR，Canvas 2D 看不到。
实机对照确认两条路径的输出确实不同。此前将 Canvas 2D 绘制后的低峰值读回解释为
“网页没有高光输入”，这个判断不成立，现已更正。

| 同一原版 TestUFO 图案 | 实机数据 |
| --- | --- |
| Canvas 2D | `rec2100-pq`、unorm8、`globalHDRHeadroom=0`，最高 PQ 通道约 0.58447，约对应 211 nit 内容通道值 |
| WebGL | WebGL2、RGBA16F、`configureHighDynamicRange({mode:'extended'})`，最高 PQ 通道约 0.82764，约对应 2004 nit 内容通道值 |
| Canvas 2D，仅诊断时放开 `drawImage` 的 HDR headroom | 同一图案恢复约 0.82764～0.83154 的高光编码，未改变图案或源图像 |

原因在于 Chromium 157 的 Canvas 2D 默认将 HDR 绘图映射到 SDR；其
[`CanvasRenderingContext2DState` 默认值](https://github.com/chromium/chromium/blob/157.0.8103.38/third_party/blink/renderer/modules/canvas/canvas2d/canvas_rendering_context_2d_state.h#L396)
明确设置 `global_hdr_headroom_=0`，绘图状态的 image flags 使用该值。
TestUFO 的 Canvas 2D 创建代码没有调整它，WebGL 则显式请求 extended HDR 和
浮点缓冲。五级灰阶工具直接使用 `putImageData` 写入 PQ 像素，没有经过这条
`drawImage` 色调映射路径，因此它通过不能替代 TestUFO Canvas 2D 的验收。

项目已将 TestUFO 验收指引及诊断工具默认引擎改为 WebGL。原版 Canvas 2D 的
行为仍取决于网站对 API 的调用；本轮没有注入永久兼容脚本、修改网站图案或安装
浏览器扩展。临时 headroom 对照仅用于确认原因。记录见
`artifacts/nixos-pad2pro-testufo-engines/`。上述 nit 数值来自 PQ 解码，非光学测量。

`tools/probe-chromium-hdr.py` 在独立临时 Chromium 配置中打开同屏灰阶测试，检查
8-bit standard、浮点 standard 和浮点 extended 三种 Canvas 的五级 PQ 数据，并
可选播放相同灰阶的 HDR VP9/WebM 片。它不改变 GNOME 显示模式。运行示例：

```sh
WAYLAND_DEBUG=1 python3 tools/probe-chromium-hdr.py \
  --video /path/to/hdr10-steps.webm --screenshot /tmp/hdr-layout.png \
  > /tmp/hdr-canvas.json 2> /tmp/hdr-wayland.log
```

基线已确认三种 Canvas 都保留五个不同的输入值，VP9/PQ 视频也能解码播放；
用户已目视确认四行都能分辨五级。
这些结果只覆盖应用输入和能力检测。CDP 截图会转换到普通截图色域，仅用来检查布局，
不能用截图中的白色裁剪判断屏幕实际 HDR。记录在
`artifacts/nixos-pad2pro-chromium-hdr/baseline.json`；原始协议日志留在 `.work/`。

复查 TestUFO 实际绘制的颜色和连续帧中的最大 PQ 通道值：

```sh
python3 tools/probe-chromium-hdr.py --testufo --engine webgl > /tmp/testufo-webgl.json
python3 tools/probe-chromium-hdr.py --testufo --engine 2d > /tmp/testufo-2d.json
```

五级粗灰阶不足以比较 8-bit、10-bit 或 8+4-bit 的细腻渐变。本轮没有因此重新
启用 FRC。编译期间的发热不足以诊断背光故障；按用户要求，背光修改不在本轮范围。

本轮还实测了 HDR → SDR → HDR：关闭时 Chromium 的 `dynamic-range: high` 为
false、`screen.colorDepth` 为 24；重新开启后分别为 true、30。结束后恢复原 HDR
模式与 70% 的 HDR 参考白滑块。记录见
`artifacts/nixos-pad2pro-chromium-hdr/mode-switch-results.json`。
当前已验证原生和浏览器的粗灰阶层次及本轮模式切换；尚未测量绝对亮度或广色域色准，
元数据差异也保留为独立准确性问题。
