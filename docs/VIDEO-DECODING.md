# 视频硬件解码

日常配置通过 `modules/video-decoding.nix` 为 mpv 使用修补后的 nixpkgs FFmpeg，
通过 `modules/chromium-hdr.nix` 为 Chromium 设置运行时硬解参数。
`modules/firefox-video.nix` 为 Firefox 启用独立 Iris VA-API 驱动及共享默认设置。
设备的视频解码器是 Qualcomm Iris；Adreno 负责画面渲染。Vulkan 视频解码扩展
当前不可用，播放器使用 V4L2 路径。

## mpv

系统 `/etc/mpv/mpv.conf` 和两种 HDR 播放配置均设置
`hwdec=v4l2m2m-copy`。正常从桌面或终端打开视频即可；未被硬件支持的编码仍可
回退到软件解码。字幕、底部留白及视频输出参数不改变解码器的选择。

排查时可以禁止回退，避免把软件播放误认为硬解：

```sh
mpv --hwdec=v4l2m2m-copy --hwdec-software-fallback=no '视频文件'
```

终端中可以直接显示实际解码路径：

```sh
mpv --term-status-msg='hwdec=${hwdec-current} time=${time-pos} drops=${frame-drop-count}' '视频文件'
```

应确认实际的 `hwdec-current`、视频帧格式及持续推进的播放时间，同时检查日志
没有解码错误。`VO: gpu-next` 本身只说明输出方式。
`v4l2m2m-copy` 会将解码结果交给播放器上传渲染，并非零拷贝显示。
请在已登录桌面的普通用户会话中运行播放器，让 logind 提供视频设备访问权限。

FFmpeg 修补内容：

- 将 V4L2 P010 映射为 FFmpeg P010LE，并初始化单内存平面布局中的色度指针。
- 等待 `SOURCE_CHANGE` 后按实际位深分配输出缓冲；处理同时出现的 `POLLPRI` 和
  `POLLERR`，避免按占位 NV12 格式分配 10-bit 视频的缓冲区。
- 以正整数标记关联输入包和输出帧，保留原始 PTS，避免负时间戳回绕。
- seek/flush 时释放旧队列，在下一次解码时重新初始化，保持旧帧引用的生命周期。

补丁保留 FFmpeg 的完整功能和当前 nixpkgs 工具链，通过 mpv 的包依赖接入。

## Firefox / VA-API

Firefox 使用 nixpkgs 原版浏览器及其 VA-API 后端，不编译或修改浏览器源码。
`packages/iris-vaapi.nix` 独立构建公开上游 `qualcomm-iris-vaapi`，源码提交和
固定摘要见 `packages/iris-vaapi/source.json`；不读取其他发行版的工作区或产物。
通过 `hardware.graphics.extraPackages` 安装驱动及
`msm_drv_video.so → v4l2_drv_video.so` 发现链接，libva 自动加载它。
实际路径是 Firefox → VA-API → Iris VA 驱动 → V4L2 → Iris 硬件。

系统默认启用 `media.hardware-video-decoding.enabled` 和
`media.ffmpeg.vaapi.enabled`，关闭尚不支持的 Vulkan Video 解码路径。
这些是可由用户覆盖的默认偏好，不绑定账户，不修改个人配置文件，不关闭
Firefox 的 RDD 沙箱，也不强制忽略硬件屏蔽项。
启用或更新后完全退出并重开 Firefox，使驱动和默认偏好生效。

AV1 暂时保留软件解码。SM8750 的 Firefox 测试中，上游驱动宣告 AV1 后出现
CAPTURE 错误、surface 同步超时和软件回退，因此本地补丁移除 AV1 解码与导入
能力的宣告；浏览器自身的 AV1 支持仍保留。
驱动也可能枚举编码入口，但本项目此次验收针对视频解码，不作为硬件编码验收。
VA-API 与零拷贝并非同义词；驱动会按格式、缓冲布局与客户端生命周期选择
直接导出、导入或复制路径，不以接口名称断言端到端零拷贝。

检查驱动加载与能力：

```sh
vainfo --display drm --device /dev/dri/renderD128
```

这只能确认驱动初始化。验收还需 Firefox 的实际 VA-API 出帧日志、持续推进的
视频时间和画面、Iris 活动、跳转及结束后重播，不能只看 GPU 合成或能力列表。

## Chromium

ARM64 nixpkgs 已编译 `use_v4l2_codec=true`；本项目额外启用运行时功能
`AcceleratedVideoDecoder`，保留原有 Wayland 和 HDR 功能开关。
默认直接使用当前 nixpkgs 的未修改浏览器及 sandbox，仅生成带启动参数的 wrapper，
不维护 Chromium 源码补丁，也不因本项目的硬解适配重新编译浏览器。
浏览器本体复用 Nix store 中的包或从官方二进制缓存下载。

H.264 已通过仅启用该 flag 的硬解验证。当前原版包的 stateful HEVC 分支返回
`kUnsupportedCodec`，且缺少单内存平面 P010 的布局处理，启动 flag 无法补齐。
这些情况暂不适配；浏览器按自身能力选择软件解码或报告不支持，HEVC 影片可使用
已修复的 mpv 播放。不要把浏览器的 GPU 渲染误认为 HEVC 硬解。

播放器的 `chrome://media-internals` 应显示实际采用的平台解码器，并且视频播放时间
与帧数持续推进。只有 `chrome://gpu` 显示硬解 enabled，或解码器初始化成功，
还不足以确认视频已经正常解码。
通过 HTTP 验证跳转时，测试服务器必须正确支持 `Range`、`206` 和
`Content-Range`；不支持范围请求的简单文件服务器会干扰跳转结果。

升级后需要退出旧 Chromium 进程再重新启动，现有进程仍使用启动时的程序和参数。

## 构建与维护

```sh
nix build .#nixosConfigurations.pad2pro.pkgs.mpv -L
nix build .#nixosConfigurations.pad2pro.pkgs.chromium -L
nix build .#iris-vaapi -L
nixos-rebuild switch --flake .#pad2pro
```

Chromium 的参数覆盖只构建轻量 wrapper，浏览器本体与 nixpkgs 的包保持相同。
部署前检查构建计划，若官方包尚未缓存且二进制缓存无法下载，应先恢复缓存访问，
不要为硬解适配在平板上编译完整 Chromium。
mpv 的 FFmpeg 补丁仍保留；更新 nixpkgs 后若源码接口发生变化，应前移该补丁
并重新验证。该方案可能重建 FFmpeg/mpv，但不会因此重建 Chromium。
Iris VA-API 包运行上游 Meson 测试和含独立软件解码参考的 AV1 位流检查。
测试临时数据放在 Nix 构建目录，不依赖维护者的家目录。

mpv 的解码验证应覆盖 H.264、HEVC 8-bit/10-bit、实际图像、播放时间、seek 和结束后重播；
Chromium 默认方案验证 H.264，HEVC 硬解属于暂不适配的范围。
HDR/Dolby Vision 显示、音频格式支持及文件传输速度分别需要对应验证。

## 实机验证：2026-11-15

本轮环境为 Linux 7.3.4-erhai-p5、FFmpeg 9.0.2、mpv 0.42.0。
完整 FFmpeg 构建的上游 FATE 测试、mpv 构建检查和 flake 配置检查通过。
从 4K Main10 样本读取出的 P010 硬解帧与软件参考逐字节一致，Y/U/V 三个
分量的 PSNR 均为无限大。

两部实际 HEVC 影片分别为 UHD Blu-ray HDR 与 WEB-DL DoVi/HDR10。
使用 Wayland/GPU 实播，保持音频解码并静音，禁止软件回退：

| 检查 | UHD Blu-ray | WEB-DL |
| --- | --- | --- |
| 实际硬解路径 | `v4l2m2m-copy` | `v4l2m2m-copy` |
| 解码图像 | 3840×2160 P010 | 3840×2160 P010 |
| 渲染/解码掉帧 | 0 / 0 | 0 / 0 |
| 最大绝对 A/V 时间差 | 0.000030 秒 | 0.000020 秒 |
| 连续播放、前后跳转 | 通过 | 通过 |
| 结束后跳转并重播 | 通过 | 通过 |

跳转覆盖约 4800 秒及返回约 10 秒；截帧目视检查未见色度错位。
单独的 FFmpeg 检查覆盖负 preroll、4800 秒 PTS 和循环解码。
不受硬件支持的 MPEG-4 样本能正常回退到软件解码。

测试时 GNOME HDR 关闭，自动桌面播放器选择 HDR→SDR 配置并成功硬解。
以上结果验证视频解码，不作为原生 HDR 输出或 Dolby Vision 显示验收。

此前曾验证过带源码补丁的 Chromium HEVC 8-bit/10-bit 硬解，但该方案需要
完整浏览器构建，现已搁置并移除对应打包代码和补丁。历史测试不代表当前默认包
具有这些能力；默认保留仅依靠运行参数即可工作的 H.264 硬解。

MPV 修复已通过 `nixos-rebuild switch` 部署到设备，无需更换内核。部署后使用系统
默认 `mpv` 播放两部完整原片，保留用户的字幕与底部留白参数，不传入 `--hwdec`
或 `--no-config`；两部均持续采用 `v4l2m2m-copy`、3840×2160 P010，
连续播放、前后跳转及结束后重播通过，渲染与解码掉帧均为零。
切换后系统没有失败的服务，账户数据库与切换前备份一致。

随后已切换到仅含启动参数的 Chromium 默认方案。求值确认浏览器本体的 derivation
与当前 nixpkgs 官方包完全一致，直接复用设备上的包，未编译浏览器源码。
使用切换后的系统 Chromium 157.0.8103.50 和隔离测试配置实际播放 H.264：
`V4L2VideoDecoder`、`kIsPlatformVideoDecoder=true`，记录到 25 个不同的呈现时间
和 3 幅不同画面，播放与跳转通过，没有管线错误或损坏帧。
此轮切换保留了相同的修补版 mpv 包及默认硬解参数，系统服务与账户检查通过。

## Firefox / VA-API 实机验证：2026-11-17

Linux 7.3.4-erhai-p6、Firefox 160.0、libva 2.24；Iris VA 驱动的全部 25 项
上游 Meson 测试通过。使用设备当前内核对应的 `pad2pro-build` 配置部署，
内核载荷保持相同，未重编译 Firefox 或 Chromium。

切换后以系统默认 Firefox 在 Wayland 桌面实播，不传入测试专用的
`LIBVA_DRIVERS_PATH`，也不通过自动化覆盖硬解偏好：

| 样本 | 实际路径 | VA-API 出帧日志数 | Iris 中断增量 | 播放、跳转、结束后重播 |
| --- | --- | --- | --- | --- |
| H.264 1920×1080 8-bit | VA-API / Iris | 247 | 532 | 通过 |
| HEVC 1920×1080 10-bit | VA-API / Iris | 237 | 754 | 通过 |
| VP9 1280×720 8-bit | VA-API / Iris | 242 | 508 | 通过 |
| AV1 1280×720 8-bit | 软件解码 | 0 | 0 | 通过 |

前三项 Firefox 日志均确认 `IsHardwareAccelerated=true` 并持续输出 VA-API 帧。
每项记录到 7 幅不同的视频画面与持续推进的呈现时间，没有视频元素错误；
测试包含截图和像素读取，记录到 4–6 个呈现掉帧，不作为零掉帧结论。
该轮样本均为 8 秒，用于验证接入和播放生命周期，不代表任意网站或长视频验收。

同一批 H.264、HEVC 10-bit、VP9 样本分别经 FFmpeg VA-API 硬解和软件解码，
各 192 帧的逐帧像素 MD5 完全一致。默认 Firefox 的 RDD 沙箱保持启用，
没有设置硬解强制启用或屏蔽项绕过。MPV 与 Chromium 包保持不变；
切换后系统服务及账户数据库检查通过。
