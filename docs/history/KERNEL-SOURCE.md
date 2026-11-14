> 历史材料，不作为当前维护指令或依赖定义。当前结构见 [DEVELOPMENT.md](../DEVELOPMENT.md)。

# 内核源码与维护

2026-11-13 正在迁移到官方 Linux 7.3.4 + 独立设备补丁集，当前代码及验收进度见
[补丁集迁移](../KERNEL-PATCHSET.md)。本文以下的 fork 包名、固定源码及历史闭包属于
对应日期的记录，已移除的旧构建入口不代表当前 flake；本轮尚未切换实机默认内核。

2026-11-12 当前日常基线为 `upstream4`，固定共享源码
`efc39b9d972665c270adc4e4ec2c46685792ffda`，在上游合并和分范围扫描基础上，
按原厂出货配置补齐 OPD2413 的 2.4/5 GHz 频率限制。两次普通全频扫描约
9.58／9.81 秒完成，200 次网关 ping 无丢包，一次实际 s2idle 恢复后自动恢复联网。
当时用户确认显示、触控、音频和蓝牙正常。以下实机验收描述属于当时的构建记录；
当前所有内核包均使用滚动工具链，记录不限制后续构建产物。
验收范围和限制见 [原厂策略适配](../WIFI-OEM-POLICY.md)。

旧 `brahma1` 源码变体使用 `40f9157a…` 加 DPU/Brahma 补丁。原固件来源见 [原厂蓝牙方案](../BLUETOOTH-OEM.md)。
旧 color1 源码/配置变体同样使用当前工具链构建。

内核 fork 为 https://github.com/ZEGEIZI/linux-sm8750-erhai ，用于多个发行版。
旧 `brahma1` 构建固定使用历史标签 `archive/nixos-pad2pro-wifi1` 中的提交
`40f9157a563afa50bdfa8e823efc1839cd12b040`。基于原实机内核的上游提交
`870167fad062e74f6de27e76db84d17cc49d8b84`（Linux 7.2.15），没有追踪更新的上游分支。
`flake.lock` 同时锁定源码内容哈希；分支名称仅供浏览，不用于决定构建版本。
原 wifi1 开发分支已于 2026-11-12 从本地及 fork 删除；
其提交仍是当前个人分支的祖先，并由上述远程标签保留。

这个历史提交包含两项驱动补丁及 `arch/arm64/configs/erhai-nixos.config`：

- ath12k 在 OPD2413/WCN7860 上使用 OEM 固件命名空间，包括 BDF 回退路径。
- CPS8601 使用可选固件请求，区分缺失与其他错误，并保留原厂固件。
- NixOS 配置片段声明存储、命名空间、cgroups、防火墙、zram、USB NCM 和内建 Wi-Fi。

## 本地源码与发行版边界

完整本地源码位于 `/zpool/storage_01/build/LinuxForOneplus/linux-sm8750-erhai`，
本地开发分支为 `erhai-personal`。这个目录与 NixOS 项目并列，
驱动、设备树和硬件基础配置可被其他发行版直接复用。

NixOS 的配置片段在本项目 `packages/nixos.config`，打包、服务、initrd 和
kShimC 启动发布也由本项目维护。历史内核提交中的 NixOS 片段不再作为新构建的
配置来源；本地多发行版分支移除了该重复片段，将 OPD2413 硬件标识纳入设备树。
共享分支已完成两个本地提交：

- `cd2d4ccd`：OPD2413 原生设备身份、板级 DPU 8bpc 抖动及绑定、自测，
  CPS8601 模块版本去除发行版名称。ath12k 与 CPS8601 行为修复已在父提交中。
- `22674ec24224cd0fc5305484f9181e1aed79692b`：通用 Kbuild 文档及仓库职责，
  移除内核仓库内重复的 NixOS 配置与旧文档。

以上提交已于 2026-11-12 随 `erhai-personal` 分支推送到自己的 fork。
同次推送还包含 `bfab2f687`，保存原工作区内的 OPD2413 Brahma 驱动、UART、
设备树、绑定、文档和协议自测。该提交是源码保存检查点，不代表共享分支已完成新的
完整内核构建或实机验收；后续 `upstream3` 的构建和实机结果见本文开头。
迁移初期没有改变实机基线，后续才按显式验收流程升级。
NixOS 中的 ath12k、CPS8601、DPU 补丁仍保留，用于重现旧的已验收闭包，
不能在构建迁移后的源码时重复应用。

内核本地分支的 `Documentation/arch/arm64/erhai.rst` 提供标准 Kbuild 构建说明，
无需 Nix。各发行版自行选择配置、内核版本后缀、固件打包、initramfs 和启动安装方式。
NixOS 中已验收的 `-nixos-erhai-…` 版本后缀仅属于本发行版的历史模块 ABI 标识，
不作为共享内核对其他发行版的要求。

历史 `brahma1` 构建使用固定 `40f9157a…` 加已记录的补丁导出，不依赖本地工作目录。
显式新内核构建已单独固定到包含原厂频段策略的 `efc39b9d9…`，不重复应用 DPU/Brahma 补丁。
直接编译完整共享源码树时，使用该仓库中的标准 Kbuild 说明。若将 Nix 源码输入
替换为已经集成 DPU/Brahma 的共享提交，也必须同步移除对应外部补丁，不能重复应用。

原配置从上游固定提交取源码后，会在 Nix 构建阶段应用本地补丁和配置片段，
并非未经修改的上游内核。此次将修改纳入自己的 fork，构建新源码时不再重复打补丁。
固定的历史源码尚需由 NixOS 模块补上 OPD2413 identity overlay；本地内核分支已直接
提供该标识。initrd 固件和 kShimC 启动集成仍由 NixOS 模块负责；
固件二进制仍是独立的固定哈希输入，没有提交进内核仓库。

## 日常用户空间维护

```sh
sudo nixos-rebuild switch --flake path:/etc/nixos#pad2pro
```

`pad2pro` 和 `pad2pro-build` 均选择 `packages.x86_64-linux.kernel`，
读取当前 `packages/nixos.config`，启用 sched_ext 和 BTF；两者及所有其他内核变体
统一使用当前 `nixpkgs` 的编译器、binutils、pahole 和模块聚合工具。
没有独立旧工具链输入，也没有通过历史 store 路径断言阻止内核或模块重建。
`docs/history/kernel/validated-kernel.json` 等文件仅为历史实机结果记录，不参与构建门禁。

```sh
nix flake update nixpkgs
```

该命令更新滚动工具链与用户空间依赖，之后任何内核包都可能重建。
`flake.lock` 记录当前选中的快照，当前 GCC 为 16.2.0、binutils 为 2.46。
各内核变体仍可选择各自的源码提交和配置，这些选择不指定旧编译器。
固件及 kShimC 安装器打包排除 Python 缓存，避免无关缓存改变构建输入。

内核及用户空间的编译架构不变：电脑交叉编译 ARM64 内核，平板本机维护时需要
可用的 x86_64 构建器或事先传入构建结果。编译结果、模块与新工具链的兼容性
通过实际构建检查，工具链更新不等同于已经完成新内核的实机测试。

2026-11-12 已核对全部 7 个内核包均选用 GCC 16.2.0，输入列表不再包含独立旧工具链。
日常与候选系统 derivation 求值通过，模块聚合来自当前 nixpkgs；
upstream4 配置已用 GCC 16.2.0 完成生成，78 项 Python 回归测试通过。
项目与平板 `/etc/nixos` 已移除旧工具链绑定；本轮未完整编译或切换运行内核。

## eBPF 代理与 sched_ext 候选配置

`packages/nixos.config` 为显式新内核启用 dae、doona 的 honk 后端及
scx/sched_ext 所需的配置：完整 DWARF/BTF 和模块 BTF、BPF JIT、cgroup BPF、
TC classifier/sockmap、TCX/netkit/veth、NFQUEUE，以及 kprobe/uprobe/ftrace。
`SCHED_CLASS_EXT=y` 提供 BPF 调度器入口，`KALLSYMS_ALL` 和函数跟踪用于
需要这些能力的 scx 调度器。BPF 程序和代理服务仍需在用户空间安装、配置并启动；
启用内核能力不会自动切换调度器或接管网络。

候选内核版本为 `7.2.15-nixos-erhai-efc39b9d9726-upstream4-ebpf1`。
`packages/kernel.nix` 的 `enableBtf` 参数为候选配置生成阶段提供宿主机
`pahole`，供 Kconfig 检查 BTF 工具版本；内核编译阶段继续使用 Nixpkgs
已有的 pahole 构建依赖。上游 firstboot 片段禁用调试信息的选项由本项目覆盖，
无需修改共享内核仓库。

在电脑上构建候选内核或完整系统：

```sh
nix build .#packages.x86_64-linux.kernel
nix build .#nixosConfigurations.pad2pro-build.config.system.build.toplevel
```

本候选已通过 Nix 配置生成、`olddefconfig` 及全部片段要求检查，确认所需选项
没有被依赖裁剪。日常 `pad2pro` 选择当前 `kernel` 源码/配置，所有变体均使用
当前工具链。2026-11-13 已完成完整内核/模块构建并实机启动，确认 BTF 可用，
`scx_lavd --powersave` 已加载运行，sched_ext 状态为 enabled；详见 [SCX 配置与验证](../SCX.md)。
dae、doona 等代理流量未在本轮验证。历史配置和实机记录不作为阻止工具链升级的约束。

## 个人 fork 同步上游

内核仓库的 `origin` 是自己的 `ZEGEIZI/linux-sm8750-erhai`，`upstream` 是
原作者的 `https://github.com/yzddmr6/linux-sm8750-erhai.git`。
日常个人开发使用 `erhai-personal`，跟踪
`origin/erhai-personal`。无需向原作者提交 PR。

仓库已设置 `remote.pushDefault=origin` 和 `pull.ff=only`。普通 `git pull`
只从自己的对应分支拉取，遇到分叉会停止；同步原作者的更新使用显式 `fetch` 和
`merge`，保留个人提交和已发布历史。`fetch` 本身不会修改工作区文件。

同步前先用 `git status` 检查并提交自己的修改。首次自行提交或合并前，在内核仓库
设置自己的 `git config user.name` 和 `git config user.email`；本次保存提交仅用
命令级配置沿用了此前的 `Codex <codex@openai.com>` 身份，没有设置全局身份。

```sh
cd /zpool/storage_01/build/LinuxForOneplus/linux-sm8750-erhai
git switch erhai-personal
git status
# 先提交未保存的个人修改，确认工作区干净，再执行：
git fetch upstream
git log --oneline HEAD..upstream/erhai/v0.7
git merge --no-ff upstream/erhai/v0.7
# 合并成功并完成所需检查后：
git push origin erhai-personal
```

合并有冲突时，修复冲突后用 `git add <已修复文件>` 和 `git commit` 完成合并；
决定放弃本次合并则用 `git merge --abort`。不要用上游分支强制覆盖个人分支。
上游默认分支可能改名，日后可通过 `git ls-remote --symref upstream HEAD` 核对。

2026-11-12 整理时，上游及自己 fork 的 `erhai/v0.7` 都为 `fb18d39b1`，
它相对个人分支有 30 个独有提交。首次整理只抓取上游；随后按用户要求，
已在 `erhai-personal` 的合并提交 `853b84e1b190dbd13dc38c16ed1eeee4fe63e6a5`
中合入这些更新，保留原个人提交历史。合并的两个父提交分别为个人分支
`bfab2f687de866c56e4528640d6a210d6fc25a5d` 和上游
`fb18d39b1baeeac3698a8786c134a326235ead9f`。
此前约 05:33 的 `git pull` 也只更新了远程跟踪引用：当时当前分支没有跟踪分支，
HEAD 未移动，个人代码未被合并或覆盖。

本次处理了 `AGENTS.md` 和板级设备树两处冲突。个人 fork 保留跨发行版职责及
合并工作流，上游贡献指南保留供将来明确要求的上游投稿使用。设备树的根
`compatible` 和新增的 `qcom,mainline-compatible` 都包含 `oneplus,opd2413`，
避免 ABL 身份恢复去掉 ath12k 与 OEM 蓝牙 UART 依赖的板型标识。
上游 UART 关机中断排空修复也与原 UART 改动一同保留。

合并检查使用 ARM64 LLVM 工具链，配置来自共享 peripherals、erhai-firstboot、
可选 sm8750-virt 及本项目当前 `packages/nixos.config`；最终配置检查通过。
板级 DTB、蓝牙、UART、ABL 身份恢复、Gunyah、ARM64 fault、充电及相关音频对象
编译通过，无编译警告。编译后的 DTB 已核对身份、OEM 蓝牙、DPU opt-in 和
Gunyah 保留内存。Brahma 协议／传输检查（ASan/UBSan）、DPU 策略、ath12k OEM
固件路由与 CPS8601 八项离线故障场景均通过。构建与配置日志位于
`/zpool/storage_01/build/LinuxForOneplus/kernel-git-backups/20261112-upstream-merge/`。
这些检查不包含完整 Image／模块最终链接、设备树 schema 校验或新内核实机验收，
没有修改本项目源码锁、冻结配置、已验收闭包或平板启动产物。
合并前个人分支另由远程标签 `archive/erhai-before-upstream-20261112` 保留。

清理前的个人分支由远程标签 `archive/erhai-before-cleanup-20261112` 保留。
原工作区 10 个修改／新增文件的补丁、文件归档、SHA-256 清单及 Git 元数据备份位于
`/zpool/storage_01/build/LinuxForOneplus/kernel-git-backups/20261112-055831`，
已核对备份及新提交的文件内容一致。该目录是改动备份，不是完整内核仓库镜像。
旧 wifi1 提交还可通过 `git switch -c wifi1-archive archive/nixos-pad2pro-wifi1`
恢复为本地分支。

同步源码不会自动更新本项目的固定提交、冻结内核配置或平板启动产物；
需要替换实际使用的内核时，仍按下面的显式构建及实机验收流程处理。

## 显式内核构建

```sh
nix build .#packages.x86_64-linux.kernel -L
nix build .#nixosConfigurations.pad2pro-build.config.system.build.toplevel -L
```

`personal-kernel-source` 固定为个人分支提交
`efc39b9d972665c270adc4e4ec2c46685792ffda`，在前述修复之上按原厂
`BandCapability=3` 增加 OPD2413 2.4/5 GHz 板级频率限制，只用于显式新构建及对应源码检查。
`upstream1-kernel-source` 保留合并提交 `853b84e1b…`，供重现上一轮测试内核。
`kernel-source` 的历史 `40f9157a…` 输入继续供冻结 `brahma1` 使用。
历史锁节点和冻结配置仍保留。候选测试期间不改变旧基线；`upstream3` 通过
实机验收后，才将它独立冻结、更新 `docs/history/kernel/validated-kernel.json` 并调整日常选择。

显式新构建读取本项目当前 `packages/nixos.config`，源码已经集成 ath12k、
CPS8601、DPU 与 OPD2413 Brahma 修改，因此不再重复应用这些补丁。
版本标识为 `7.2.15-nixos-erhai-efc39b9d9726-upstream4-ebpf1`，同时构建匹配的
CPS8601 覆盖模块。版本中的源码标识是包参数，历史包仍保留原默认值。
`pad2pro-build` 保留当前 native-gamma HDR 桌面和 OEM 蓝牙固件，用于完整系统
实机测试；probe 也选择相同候选内核和匹配固件。
当前配置的后续修改不会自动改写日常已验收基线。

`upstream1` 已完成完整构建、RAM／共享分区启动，用户确认显示、触控和蓝牙播放正常；
但旧、新内核均复现 5200 MHz 热点发现延迟，因此没有提升为日常基线。
`upstream2` 完整 Image、1285 个模块和 CPS8601 覆盖模块均已构建，测试系统已组装。
已通过临时镜像启动并核对版本，但约 41 至 161 秒仍未自动发现目标；单频扫描可以恢复。
`upstream3` 改用匹配该固件硬件模式的分范围扫描，完整构建、临时启动及普通共享分区
启动均通过，24.10／33.28 秒的首次观测均已自动连接 5200 MHz。它作为上一日常基线继续保留。
`upstream4` 的完整内核、1285 个模块、CPS8601、initrd 和系统已构建，临时镜像已发送。
独立 `upstream4-kernel-source`、`docs/history/kernel/configs/upstream4.config` 和
`upstream4-kernel` 包保存相同输入，其输出已核对与实测闭包一致；本轮扫描和
挂起恢复验收通过后，日常选择和已验收清单更新到 upstream4。
原厂依据及 20 秒取消发起方的证据见 [原厂策略适配](../WIFI-OEM-POLICY.md)。
参考补丁及证据见 [扫描延迟调查](../WIFI-SCAN.md)；状态见
[验收记录](../KERNEL-UPSTREAM-VALIDATION.json)。

Wi-Fi 路径检查和 CPS8601 故障注入检查直接读取锁定源码里的实际函数。
内核配置生成阶段继续检查所有设备及 NixOS 片段请求。源码迁移的离线检查不能替代
新内核的实机启动、USB SSH 和 Wi-Fi 验收。实际验收结果应记录到验证文档；
构建不再要求产物等于历史闭包路径。

早先的仓库迁移本身没有部署；后续 brahma1 已完成构建、启动发布和实机重启。

## 2026-11-12 迁移核对

已将共享树的五个相关源码／设备树文件与 `870167fad062` 加旧补丁的结果核对。
除 OPD2413 原生身份、CPS8601 的通用模块版本和空白格式外，内容一致。
Wi-Fi 路径检查、CPS8601 八项故障注入、DPU opt-in／bridge 引用／6、8、10bpc
策略检查均通过。检查不构建或部署完整新内核，也不替代实机验收。

早先迁移时原始冻结配置、三个历史补丁及基线清单未改动。后续原冻结配置和
历史补丁仍保留；当时 `docs/history/kernel/validated-kernel.json` 更新到 brahma1，当前则在新的
实机验收后更新到 upstream4。
Mutter、Mesa、蓝牙地址服务和 kShimC 都保留在各自项目；当时尚未引入 ArmadaOS
Brahma 蓝牙驱动或其固件；本次已按上面的新基线完成移植。
