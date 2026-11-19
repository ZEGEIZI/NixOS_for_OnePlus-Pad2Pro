# 参考项目功能对照

对照日期为 2026-11-18，参考版本为 `fad774fa045256d63cf6b11ae9be7a1dcb58efb5`。
已有功能包括 USB-C 外屏画面与声音、手写笔压感、有线快充、合盖休眠、
键盘输入、内置音频、硬件视频解码和系统代际回退。参考项目使用 APT 发布，NixOS
通过 flake 构建和 kShimC 代际发布。 [参考版本](https://github.com/yzddmr6/onepluspad-2pro-mainline/tree/fad774fa045256d63cf6b11ae9be7a1dcb58efb5)

## 桌面与设备支持

| 功能 | NixOS 实现 |
| --- | --- |
| 蓝牙键盘套 | Esc 通过 systemd hwdb 映射，蓝牙触控板通过 libinput 识别为按压式触控板，支持按住拖动。 |
| 前后摄像头 | libcamera 为 SC820CS 和 SC1300CS 分别加载软件 ISP 调校。GStreamer 应用和 WirePlumber 使用这两份配置。 |
| 后摄点按对焦 | 应用列表中的「后摄对焦相机」打开后摄并对画面中央对焦，点按画面可重新对焦。快门将照片保存到用户的图片目录。 |
| 登录界面亮度 | GDM 默认关闭环境光自动调节，保留 systemd 恢复的背光亮度，用户登录后使用个人设置。 |
| 内部 UFS 分区 | udisks 隐藏内部 UFS 的 Android、固件和其他非 Linux GPT 分区。外部 USB 存储仍按正常规则展示。 |
| 手写笔吸附蓝牙连接 | p8 内核校验磁吸充电线圈收到的笔地址，系统服务只对该地址发起配对和连接。BlueZ 处理 HID 和标准电量上报。 |
| USB 光驱 | p8 增加 SCSI 光驱、ISO 9660、Joliet 和 UDF 支持。 |
| 自动旋转与自动亮度 | SSC 经 FastRPC、libssc 和 iio-sensor-proxy 接入 GNOME。亮度采用 OPD2413 的原厂 lux 曲线，GNOME 继续处理亮度偏置与屏幕方向。 |
| 扬声器随方向调整 | 四声道 AudioReach PCM 和 PipeWire 滤镜将内屏方向映射到四角扬声器，DisplayPort 和 USB 输出使用各自的节点。 |
| 双 LED 手电筒 | p9 启用 PM8550 双发光单元，GNOME 快捷设置提供开关和调光。调光经当前会话的 logind 接口，最高档使用驱动量程的 80%。 |
| 暂停充电 | p9 为板载电池提供 `charge_behaviour`。接电时可从顶栏充电菜单暂停充电，选择写入平板本地状态并在开机时恢复。 |

手写笔服务遵循蓝牙开关，可以通过 `hardware.oneplus-pad2pro.pen.autoConnect`
调整。笔的配对仍由 BlueZ 保存在本机。

## SSC 校准数据

新安装可从这台平板自己的 Android `persist` 分区读取校准。安装带 SSC 支持的配置后，
在平板上以只读方式挂载分区并导入。导入工具只复制传感器 registry 和版本文件。

```sh
mount_dir=$(mktemp -d)
run0 mount -t ext4 -o ro,noload /dev/disk/by-partlabel/persist "$mount_dir"
run0 erhai-sensors-import-registry "$mount_dir/sensors"
run0 umount "$mount_dir"
rmdir "$mount_dir"
```

下一次正常启动时，FastRPC 文件服务读取 `/var/lib/erhai/sensors` 中的本机校准。
在 GNOME 快捷设置关闭旋转锁定，在「设置 → 电源」打开自动亮度。

## 未纳入本轮移植

| 功能 | 当前技术差异 |
| --- | --- |
| 90 Hz 内屏模式 | 需要验证本项目 XN242 面板、DSC 及 HDR 在切换刷新率时的组合行为。 |
| Waydroid、GunyahVM | 当前内核关闭 Binder 和 Gunyah 客体管理。Waydroid 的 Adreno 830 加速还需要 Android 用户空间图形驱动，GunyahVM 还需要独立的 Nix 打包和客体启动验证。 |
| CPS8601 固件升级 | 当前实机运行工厂版 `0x011e`，与参考归档映像版本相同。参考归档会在版本不同时触发写入，需先核对其他固件版本的升级路径。 |

## 验证

平板在 libcamera 0.7.2 下加载了两份 ISP 调校。以 640×480 连续测试前摄、后摄、
再开前摄，每次收到 8 帧，约 30 fps。「后摄对焦相机」的 1280×960 预览管线
也收到图像帧。测试未保存画面，点按对焦和拍照仍待交互验收。

实机校验了 Esc 的 hwdb 匹配、libinput 规则语法和 UFS 分区的 udev 规则。
GDM 亮度默认值读回为 `false`。键盘套实际按键和拖动仍待验收。
110 项回归、设备回归、p8 补丁集严格重放和完整系统构建通过。

平板已激活第 68 代，kShimC 当前项为 `nixos-be7cb7935543dc9153b1e650529225a7`，
启动载荷摘要校验通过。用户空间已切换，平板仍运行 p7。
p8 在下次启动后生效，磁吸首次配对和真实 USB 光驱读盘仍待验收。

### p9 实机记录

第 69 代已实际启动 p9。此次通过只读挂载导入本机的 SSC 校准。
采样门控收到 132 个加速度样本，其中 130 个符合重力范围。传感器代理报告
`left-up`，Mutter 报告对应的 90° 变换。约 36 lx 时，GNOME 设置服务通过 D-Bus
发送约 18% 的目标亮度。

48 kHz 双声道测试流经 PipeWire 旋转滤镜到四声道扬声器 PCM。四个路由增益符合
90° 变换，硬件帧计数推进。双 LED 分别经 logind 写入低档，读回两个亮度均生效，
随后关闭。GNOME 两个扩展均为 ACTIVE。

暂停和恢复已通过桌面用户的 polkit 路径写入并读回，恢复服务也读回了已保存的选择。
验证期间未接有线电源，实际充电电流和四个方向的逐路听音仍待验证。
完整系统构建、内核严格重放、设备回归和 112 项项目测试通过。
