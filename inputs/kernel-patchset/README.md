# linux-sm8750-erhai-patchset

OnePlus Pad 2 Pro（OPD2413 / Erhai / SM8750）的发行版无关内核补丁集。
只维护向前升级的正式内核系列，不提供旧版本兼容分支。当前迁移目标为 Linux 7.3，
当前官方源码为 7.3.4（从 7.3.3 前移）；构建、实机验收和默认切换状态见 `provenance/STATUS.md`。

## 来源与维护入口

- 原设备树：`ZEGEIZI/linux-sm8750-erhai` 的 `efc39b9d972665c270adc4e4ec2c46685792ffda`。
- 7.2.15 仅用于差异提取，完整重建的 Git tree 相等证明见 `provenance/extraction.json`。
- 当前修改的唯一维护来源是 Git 分支 `patchset-7.3`；本机工作树位于
  `/zpool/storage_01/build/LinuxForOneplus/kernel-patchset-work/linux-7.3`。
  不重写原 `erhai-personal` 或已发布历史；未推送本次分支。
- `patchsets/7.3/patches` 与 `configs/` 均由该分支导出，禁止手工修改。
  初始提交按子系统聚合，保留源码版权／许可证；迁移自动提交不冒充原作者。
  来源提交、上游等价文件及冲突清单见 `provenance/`。历史仍有浅边界，
  `source-commits.tsv` 是可见历史记录，不能当作经过筛选的最小补丁列表。
- 保留现有平台、外设、相机／视频和可选 Gunyah 支持；后续裁剪必须单独证明依赖。
  NixOS 打包、用户空间、固件及 kShimC 发布由相邻 NixOS 项目负责。

## 不依赖旧 fork 的重建

下载官方 tarball，按 manifest 的 SHA-256 核验后执行：

```sh
python3 tools/verify.py --tarball /path/linux-7.3.4.tar.xz \
  --destination /new/replay --report /path/replay.json
cd /new/replay/linux-7.3.4
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- defconfig
scripts/kconfig/merge_config.sh -m .config \
  arch/arm64/configs/sm8750-peripherals.config arch/arm64/configs/erhai-firstboot.config
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
make -j8 ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- Image modules qcom/sm8750-erhai.dtb
```

补丁应用失败立即停止。`verify.py` 在初始基线上核对全部变更文件的结果哈希，
并确认导出配置与打补丁后的源码一致。NixOS 构建使用当前 nixpkgs 工具链。
固件及启动安装按发行版处理；单独构建 Image 不代表可直接替换平板启动项。

维护分支也可在另一个官方 stable Git 克隆中重建，无需原设备仓库：

```sh
git switch -c patchset-7.3 v7.3.4
# 在内核 Git 工作区执行；PATCHSET 指向本项目的绝对路径。
while IFS= read -r patch; do git am "$PATCHSET/patchsets/7.3/$patch" || break; done \
  < "$PATCHSET/patchsets/7.3/series"
```

## 更新与发布

1. 在当前分支提交修复；同系列更新重放到新的官方 stable tag，跨系列另建前进分支。
   比较上游行为并删除已合入补丁，不能用旧文件覆盖新接口。
2. 构建与相关驱动检查通过后，从 Git 提交导出：

```sh
python3 tools/export.py --repo /path/kernel --base v7.3.4 \
  --tarball /path/linux-7.3.4.tar.xz --version 7.3.4 --release p5
python3 tools/verify.py --tarball /path/linux-7.3.4.tar.xz --destination /new/replay
```

3. NixOS 项目执行 `python3 tools/vendor-kernel-patchset.py /absolute/path/to/this/project`，
   将已校验的发布快照保存到 `inputs/kernel-patchset`。该目录是生成产物，
   后续仅由同步工具更新；随 NixOS 配置一起分发，不依赖电脑上的 sibling 路径。
4. NixOS 显式使用 `linux_7_3`，同系列随 nixpkgs 更新。新增系列需要移植后显式选择；
   旧系列被 nixpkgs 移除时构建应失败，禁止改选更旧内核。
5. 构建完整系统／DTB／initrd，候选实机验收后再切换默认。保留既有可启动代际；
   当前源码等价证明、编译结果和实机记录分别保存。
   每次导出先将 manifest.validation 置为 pending；验收后只更新该状态元数据并引用对应
   provenance 报告，保留导出时摘要及元数据变更记录，不能手改补丁、配置或结果哈希。

`verify.py --forward` 用于同系列下一补丁版本的重放检查。它不会假称源码结果与旧版
完全等价，仍须编译及实机验收。版本、源码哈希、提交、顺序与依赖见 manifest；
验证结果保存在独立 provenance 文件，不修改生成补丁。
