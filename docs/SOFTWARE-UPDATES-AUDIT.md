# 软件更新约束扫描（2026-11-12）

> 历史扫描。当前内核、固件与 kShimC 的维护关系以
> [项目维护指南](DEVELOPMENT.md) 和 [补丁集维护](KERNEL-PATCHSET.md) 为准。

扫描范围为项目当前生效的 flake、NixOS 模块、软件打包、固件输入和构建脚本，
并通过 SSH 核对平板 `/etc/nixos` 与实际 Nix 求值。历史 `.work`、构建产物和
实机证据中的旧版本不作为当前软件约束。

结论：Mutter 和 Mesa 已没有具体版本门禁；普通用户空间跟随 nixpkgs。
项目仍存在明确的内核、硬件固件和启动菜单源码固定，因此目前不是所有组件都能
随一次 nixpkgs 更新自动升级。此扫描没有更改这些硬件组件的选择或启动配置。

| 项目 | 当前约束 | 位置与影响 |
| --- | --- | --- |
| 普通用户空间 | 来自 nixos-unstable，flake.lock 记录一次依赖快照 | flake.nix 的 nixpkgs 输入可通过 `nix flake update nixpkgs` 更新；当前没有额外的精确软件版本断言 |
| Mutter / Mesa | 已移除具体版本断言 | packages/mutter-hdr.nix、packages/mesa-erhai.nix 正常对新版应用补丁；实际补丁或 API 不兼容仍会导致构建失败 |
| 日常内核 | upstream4 源码 efc39b9d9726…、版本 7.2.15 | 使用当前 nixpkgs 工具链，更新 nixpkgs 可触发内核重建；不会自动选择新的源码提交 |
| 内核构建入口 | personal-kernel-source 为 efc39b9d9726… | pad2pro-build 使用当前 packages/nixos.config 和滚动工具链；源码引用单独更新 |
| 内核版本和本地版本后缀 | packages/kernel.nix 写死 7.2.15 和 870167fad062 | 仅更新源码输入仍不等于完整支持新版内核，需要使版本标识与源码一致 |
| 内核精确产物检查 | 已移除 | 实机验证 JSON 为历史记录，不再按历史产物路径阻止重建 |
| 内核编译和模块聚合工具 | 统一跟随当前 nixpkgs | 所有内核包都使用当前工具链，已删除独立旧工具链输入和 aggregateModules 覆盖 |
| 非 Wi-Fi 设备固件 | 从 erhai 固定提交 4cc3570c… 取得 | flake.nix、packages/firmware.nix；包括设备依赖的厂商固件集合，不跟随参考仓库新提交 |
| Wi-Fi 固件 | requireFile 指定唯一归档哈希，清单指定六个文件的大小和哈希 | packages/firmware.nix、inputs/firmware/wifi.json；来源为 OPD2413_16.0.9.400(CN01)，需要提供新的完整配套固件才能更新 |
| 通用 linux-firmware | 没有启用通用可再分发固件集合 | modules/oneplus-pad2pro.nix 的 enableRedistributableFirmware=false；设备使用上述专用固件。wireless-regdb 仍跟随主 nixpkgs |
| kShimC 菜单构建 | 固定 git archive 提交 ca1b03b809… | tools/build-menu.py 的 REVISION；更新 NixOS 不会自动重建或刷写菜单程序 |
| kShimC 发布协议辅助代码 | 仓库内随附固定来源的 boot_files.py | inputs/kshim-protocol/source.json / boot_files.py；来源提交和摘要记录其版本，Nix 打包采用当前本地文件，不自动下载新协议实现 |
| kShimC 外部构建环境 | 独立项目的构建脚本使用固定工具链镜像 image_id | 本项目从指定 kShimC 源码快照调用 tools/build_boot_tools.py；需要在独立项目中维护，不受主 nixpkgs 控制 |

## 不属于软件版本锁的配置

- `system.stateVersion = "26.05"` 是持久数据和默认行为兼容基线，不指定 NixOS
  软件包版本，不应为了更新软件改成新发行版数字。
- `system.autoUpgrade.enable = false` 只表示不执行无人值守定时升级，不妨碍手动更新。
- `flake.lock` 是可更新的依赖快照。但 `original.url` 本身写死提交或发布归档的
  输入，即使重新生成 lock 也仍会得到同一个源码；这与移动的 nixos-unstable
  输入不同。
- `kshim-install` 的 `version = "0.1.0"` 和 CPS8601 修复模块的 `version = "1"`
  是项目自有打包元数据，不阻止依赖升级。CPS8601 使用所选内核及当前工具链构建，
  不再使用历史模块路径门禁。
- Mesa 的 upstream-source.json、历史验证记录和补丁文件头中的版本号目前只是
  来源记录；没有发现继续用它们拒绝新版 Mesa 的生效代码。
- 架构、分区身份、固件完整性、启动载荷摘要以及测试中的断言不应作为一般软件
  版本限制删除。

## 达到“全局可更新”的差距

普通软件已经具备跟随 nixpkgs 更新的路径。若内核、固件和启动程序也要自由选择
新版，剩余事项主要是源码、硬件固件和启动程序的选择：

1. 为新内核提供可更新的源码引用和匹配源码的版本标识，使设备内核可构建、验收和发布。
2. 已删除所有内核变体的旧工具链依赖与历史闭包路径门禁。
3. 新工具链和模块聚合接口的兼容性通过实际构建处理，不退回固定旧工具链。
4. 为设备固件定义可更新的完整输入及来源，随更新生成对应清单和哈希；保留
   完整性校验，不将旧清单直接用于不同固件，也不把“最新通用固件”视为同机型固件。
5. 让菜单构建接受指定的新源码引用，并同步协议辅助代码及其构建环境；菜单的
   构建和刷写与 NixOS 普通软件更新分别处理。

“nixpkgs 最新版本”指该发行通道提供的版本，不保证等于每个上游项目刚发布的
最新版本。版本门禁可以移除，但不能保证跨版本的补丁、驱动接口和硬件行为永远兼容。

## 实机核对

扫描时运行系统为 `2smsmhgpra359ivda411fnc0c3a755kl`，内核为
`7.2.15-nixos-erhai-870167fad062-color1`。Nix 求值确认日常内核路径仍为
`/nix/store/ybz02789bi5m4043qvyyz08zf5y4mhjk-linux-erhai-aarch64-unknown-linux-gnu-7.2.15`，
自动升级关闭，通用可再分发固件集合关闭；本机 local.nix 仅指定 boot PARTUUID
和 USB 管理网络，没有额外的软件版本覆盖。
