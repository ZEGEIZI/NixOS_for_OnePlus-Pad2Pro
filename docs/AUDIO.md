# Pad 2 Pro 音频

2026-11-12：GNOME 已显示内置扬声器和麦克风，用户确认左右声道测试与
说话时输入电平均正常。修复已在线启用并发布到 kShimC，尚未重启验收。

## 原因与实现

原系统 `/proc/asound/cards` 为空。内核已经加载 WCD939x、SoundWire 和六颗
AW88261，但声卡探测缺少 `qcom/sm8750/OnePlus-Pad-2-Pro-tplg.bin`，
AudioReach component probe 返回 `-2`，整张声卡注册失败。
GNOME/PipeWire 因而没有任何内置播放或采集设备。

`packages/audio.nix` 使用本项目 `packages/audio/` 维护的 AudioReach m4 配方、
板级 TDM/MFC 扩展和 UCM。它们由原始来源移入，出处和许可保存在该目录的
`source.json` 与源码头；构建不再获取其他设备项目。上游拓扑归档为
`993a17dcb672357998a463a73f120064d6c74f4f`，SHA-256 在构建时核对。
使用 m4 与 alsatplg 编译并解码验证，不引入预编译拓扑。
编译提示的三个外部硬件 widget 由内核 DAI 提供；实机声卡注册成功。

`modules/audio.nix` 提供 `hardware.oneplus-pad2pro.audio.enable`；日常
`hosts/pad2pro` 开启它。拓扑安装到系统 firmware 和 initrd，UCM 与当前
`alsa-ucm-conf` 合并，保留通用设备配置。通过 `ALSA_CONFIG_UCM2` 指定
配置目录，同时写入 PipeWire、PipeWire Pulse 和 WirePlumber 用户服务，
避免仅修改登录环境后已有会话仍无法找到本机 UCM。

HiFi 先建立前端到后端的播放/采集路由，再允许 ACP 探测 PCM；
麦克风与扬声器的 EnableSequence 配置对应 codec/功放。
声卡提供 `DP0 Jack` 时，HiFi 加载 DisplayPort 路由，并在 ACP 探测前接通独立的
`MultiMedia2` 播放 PCM。PipeWire 根据插孔状态更新外屏输出的可用性。
冻结内核存在 `TX0/TX1 HPF cut off` 控件，参考 UCM 的 75 Hz 高通可直接使用；
无需采用 ArmadaOS 早期候选中缺少这些控件的兼容处理。

## 增益与边界

2026-11-14 按用户要求移除了打包阶段将功放 350 替换为 270 的额外衰减。
六路功放恢复板级 UCM 的 350（-2.5 dB），比原先的 270（-22.5 dB）提高
20 dB；这表示电平增益变化，不代表实测声压增加 20 dB。
DSP 保持 8192（Q13 单位增益），WirePlumber 对本机 Speaker 设置
`channelmix.max-volume = 1.0`，防止通过数字过放大造成削波。

原厂 DSP 扬声器振幅/音圈温度保护和逐路调音尚未实现；芯片自身保护及
软件音量上限不能替代它们。当前听音通过不代表持续大音量可靠性已验收。
USB-C 模拟耳机仍待验证。

## USB-C 外屏音频

通过支持 DisplayPort Alt Mode 的 USB-C 线缆或转接器连接带音频回放能力的
显示器。在 GNOME「设置 → 声音 → 输出」中选择「HDMI / DisplayPort audio」。
内屏和外屏的布局、分辨率及刷新率可在「设置 → 显示器」中调整。

2026-11-18 在 `7.3.4-erhai-p7` 上验证，外屏 `DP-1` 以 3840×2400、60 Hz
同时与内屏工作。PipeWire 枚举了外屏输出、内置扬声器和麦克风，
48 kHz 双声道静音测试流送至外屏 PCM，硬件帧计数持续推进。
配置已激活为平板的 NixOS 第 67 代。

## 随内屏旋转的扬声器声道

板载扬声器现在使用四声道 PCM。PipeWire 依据 GNOME 报告的内屏方向排列四角
扬声器的声道，两个高音单元分别取对应侧的均值。内屏旋转可以由 SSC 自动触发，
也可以在 GNOME 显示设置中手动切换。外屏音频和 USB 音频仍通过各自的设备输出。

## 2026-11-14 解除额外衰减的验证

- 本地音频包构建、归档校验和拓扑编译/解码通过，`nix flake check --no-build` 通过。
- 平板完整系统构建及 `nixos-rebuild switch` 成功，已发布启动代际
  `nixos-7ec3bc4552c4537a3544b9c56030142e`；未重启。
- PipeWire/Pulse/WirePlumber 重启后，Amp0/1/2/3/5/6 均读回 350，DSP 读回 8192。
- 新旧拓扑二进制 SHA-256 均为
  `d2fd46689b0232263380984cf4a23b5261a98ed68e5695b1be96a8c25f47a107`。
- 音频用户服务均 active，系统失败服务为 0；账户数据库及附属 UID/GID 范围未改变。
- 应用前将当前会话的播放音量从 100% 调为 10%，供用户自行逐步调整；没有执行满音量播放或声压测量。
- 配置和控件备份位于平板 `/var/backups/audio-gain-20261114/`。

## 初始音频接入的历史验证与回退

- 固定来源归档校验、拓扑编译及解码、完整 ARM64 NixOS 系统构建通过。
- 当前内核上补入拓扑后重新绑定此前探测失败的 `sound`，声卡注册为
  `sm8750 / OnePlus-Pad-2-Pro`；六颗功放均加载本机 ACF。
- alsaucm 的 HiFi、Mic 与 Speaker 启用序列均成功；PipeWire 列出
  `alsa_output.platform-sound.HiFi__Speaker__sink` 和对应 Mic source。
- GNOME 同时打开播放与采集，ALSA 均为 S16_LE / 48 kHz / 双声道，帧计数推进。
  用户确认输出和输入显示、左右扬声器听音、说话时输入电平均正常。
  未保存用户录音；独立录音回放、挂起恢复和冷启动仍待验收。
- 软件音量上限实际节点读回为 1.0；系统与用户失败服务均为 0。
- 60 项现有 Python 回归通过。原 77 个固件文件逐字节相同，仅新增拓扑；
  内核 Image、完整 DTB 及模块闭包与旧系统相同。
- 新旧三个启动代际的全部载荷大小/摘要通过；新载荷与系统产物一致，
  profile 与 GC root 正确，原 `boot.conf` 不变，`/boot` 恢复只读。

系统：`/nix/store/pdpyvx780wkk4gagv2cnakp2s0za4haq-nixos-system-pad2pro-26.11.20261107.f4a03c0`。
启动代际：`nixos-e843b71d8d923caa0cb9f43b9b71a989`。
前一代 `nixos-2f1ef471c080276e1b80e8f8ebcbde4c` 和原蓝牙验证代际保留。
设备上的构建/激活日志及配置备份位于 `/var/lib/pad2pro-updates/audio/`。
本次没有重启，下一次启动应选择该音频代际，再检查 GNOME 声音设备。
