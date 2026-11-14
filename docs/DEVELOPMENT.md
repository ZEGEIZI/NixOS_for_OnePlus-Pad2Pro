# 项目结构与维护

本项目负责 OnePlus Pad 2 Pro 的 NixOS 集成。设备相关的两个项目依赖为
`linux-sm8750-erhai-patchset` 和 `kShimC-oneplus-pad2-pro`；通用软件、官方
Linux 源码和工具链由 `nixpkgs` 提供。克隆本项目即取得固件和设备支持快照，
无需另外克隆参考发行版或内核 fork。

| 目录 | 职责 |
| --- | --- |
| `hosts/pad2pro/` | 日常配置及可选的本机 `local.nix` |
| `modules/` | 硬件、桌面、音频、蓝牙、initrd 和 kShimC 的 NixOS 模块 |
| `packages/` | Nix 打包、NixOS 内核配置、Mesa／Mutter 补丁及音频源码 |
| `inputs/kernel-patchset/` | 独立补丁项目生成的发布快照，含来源和验证材料 |
| `inputs/kshim-protocol/` | kShimC 协议、发布工具、许可、版本清单及本地扩展 |
| `inputs/firmware/` | 基础、Wi-Fi、蓝牙固件的逐文件清单与原始来源声明 |
| `inputs/firmware/archives/` | 随 Git 提供的三个通用固件归档，构建自动校验 |
| `tools/`、`tests/` | 本项目维护工具与回归测试 |
| `docs/` | 当前安装、更新和维护文档 |
| `docs/history/` | 原始计划、旧内核配置和补丁；不参与构建 |
| `support/` | 可供其他发行版使用的蓝牙身份服务 |

`NOTICE`、源码头和历史文档记录原始移植来源；这些归属信息不构成项目依赖。
`inputs/firmware/ORIGINAL-NOTICES.md` 是原始来源说明，其中的旧打包命令不作为
本项目操作入口。固件输入和准备方式以 [FIRMWARE.md](FIRMWARE.md) 为准。

## 更新边界

- 驱动、设备树、硬件基础配置：在独立补丁项目修改、导出、验证后，运行
  `python3 tools/vendor-kernel-patchset.py /path/to/linux-sm8750-erhai-patchset`。
  `inputs/kernel-patchset/` 不直接编辑，详见 [内核维护](KERNEL-PATCHSET.md)。
- kShimC：`inputs/kshim-protocol/source.json` 固定上游提交。运行
  `python3 tools/vendor-kshim.py /path/to/kShimC-oneplus-pad2-pro` 重建快照；
  采用新提交时显式追加 `--revision COMMIT`，审查协议变化后测试。
  `tools/build-menu.py` 使用同一提交构建菜单，NixOS 的载荷共享扩展只用于发布端。
- 音频：直接维护 `packages/audio/` 的板级拓扑和 UCM；上游 AudioReach 归档的
  版本、摘要及许可在 `source.json`。Mesa／Mutter 补丁同样在本项目维护。
- 固件：修改 `inputs/firmware/` 清单，重新生成相应归档，同时更新 `archives.json` 中的固定摘要；
  使用原始厂商文件或已保存归档，不读取其他发行版工作区。
- 系统更新：`nix flake update nixpkgs`；官方内核与工具链随之更新。跨内核系列
  先前移补丁集；不降级或新增旧系列适配。

## 验证

```sh
python3 tools/vendor-kshim.py --check
python3 inputs/kernel-patchset/tools/verify.py
nix flake check --no-build
nix build .#checks.x86_64-linux.boot-publication .#checks.x86_64-linux.firmware-inputs
nix build .#audio .#firmware .#bluetooth-firmware .#kshim-install
nix build .#checks.x86_64-linux.patchset-replay
nix build .#nixosConfigurations.pad2pro-build.config.system.build.toplevel -L
```

固件包通过共用的 `packages/firmware-policy.nix` 仅允许列出的设备固件。
完整 ARM64 用户空间构建需要 ARM64 builder 或仿真；软件安装和验证见 [BUILD.md](BUILD.md)。目录或打包变动应核对固件、
拓扑、UCM、内核补丁及启动协议的有效内容；硬件行为变更需候选实机验收。
历史验证记录不固定工具链，也不替代新版本的构建与验收。
