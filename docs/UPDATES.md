# 更新、回退与保留

2026-11-13 正在迁移到官方 Linux 7.3.4 + 独立设备补丁集，当前代码及验收进度见
[补丁集迁移](KERNEL-PATCHSET.md)。本文以下的 fork 包名、固定源码及历史闭包属于
对应日期的记录，已移除的旧构建入口不代表当前 flake；本轮尚未切换实机默认内核。

2026-11-13 zram 从物理可用内存的 25% 调整为 50%，保留 zstd 和 swap 优先级 5。
内核报告可用物理内存约 14.5 GiB，因此 zram 设备容量为 7,787,773,952 字节
（约 7.3 GiB）。生成配置和系统代际均已更新；在原 swap 使用量为 0 时停止、
重建并重新启用 zram，已核对设备容量、压缩算法及交换服务状态。账户、内核、
模块、initrd 和桌面未变，`/boot` 保持可写，失败服务为 0，未重启。
实机备份及验证记录位于 `/var/lib/nixos-zram/20261113-145322/`。

2026-11-13 `/boot` 默认改为可写，并已在实机激活：挂载选项为
`rw,noatime`，目录权限保持 `root:root 0755`。root 创建、同步和删除临时文件
通过，非特权用户的写入权限检查被拒绝；生成的 fstab、mount unit 和下一次启动
代际均已更新。此次仅替换运行系统的 fstab 依赖，保留现有桌面清理结果；
内核、模块、initrd、用户空间及账户数据库均核对未变，失败服务为 0，未重启。
实机备份及验证记录位于 `/var/lib/nixos-boot-rw/20261113-144116/`。

2026-11-12 按用户要求清除全部旧系统代际和旧内核：保留当前已启动的第 22 代
`nixos-06f3e4b35a208da7db344a74adbfc516`（`g4k4c9zyappd43ic9ndj4d0alhy14w1m`）。
已删除第 1～21 代、7 个旧启动项及 17 个旧系统测试引用，随后由标准 Nix GC
删除 5486 个不再使用的 store 路径。核对所有旧系统输出和 42 个不属于当前闭包的
旧内核相关输出均已移除；当前 color1 内核、模块及系统完整闭包仍在。
菜单 `previous=none`；`/boot` 使用量从约 661 MiB 降到 83 MiB，根分区约 7.3 GiB。
当前启动载荷摘要、只读挂载、运行系统和系统 profile 校验通过，失败服务为 0，
`boot_a` 摘要与清理前一致。未重启。原厂 Wi-Fi 固件构建输入另外保存到
`/etc/nixos/inputs/local/opd2413-wifi-firmware.tar`，避免 GC 移除唯一可重建输入。
执行记录位于平板 `/var/lib/nixos-kshim/cleanup-current-only-20261112/`，本地摘要见
`artifacts/nixos-pad2pro-cleanup-current-only-20261112/result.json`。

2026-11-12 用户空间更新策略：Mutter 和 Mesa 均移除具体版本断言，直接使用
`nixpkgs` 提供的软件版本并应用现有补丁。版本号变化不再提前阻止构建；补丁应用
或编译失败时再修复补丁。`packages/mesa/upstream-source.json` 仅保留来源记录，
不再作为版本门禁。更新命令仍为先 `nix flake update nixpkgs`，再执行下面的
`nixos-rebuild`。`flake.lock` 记录每次更新选择的依赖快照，便于复现与回退。

后续适配已发布 `nixos-5f264e38a87b90becf4b3fe8ad8d8cde`，系统为
`a1jf5iv4fw7mfyhrgk3r6pzas6mhyb59`，Mutter 为 `d240p7n8r3cykhy4l9d68vwldczn8s4b`。
日常配置默认 10bit HDR，保留运行时选择 12bit，并按实际画面高光需求调节
背光、补偿 SDR 白位。重新登录后的会话验证和用户目视检查通过，已固化到
系统 profile 和启动当前代际；前一代为下面的联合候选，冻结 color1 内核不变。详情见
[显示精度与 HDR](DISPLAY-COLOR.md)。

2026-11-11 HDR + 8+4-bit 联合输出已发布并在重新登录后的会话通过实机检查。
当时当前代为 `nixos-41550284093e0d1dd8a81eaed8dae245`，前一代为
`nixos-26ed660f4f2989b92e66e449eb329254`，其他旧代际仍保留。
当时日常 `pad2pro` 保留该 HDR/FRC 路径；`pad2pro-hdr10` 可构建关闭 FRC 的 HDR
对照。内核及其冻结闭包未替换，共享启动菜单配置未修改。完整记录见
[显示精度与 HDR](DISPLAY-COLOR.md)。

同日早些时候：平板的默认维护配置 `pad2pro` 已对齐实机运行的 `color1` 内核和
HDR 桌面，`pad2pro-hdr` 指向同一配置。此前 `nixos-rebuild switch` 按主机名
选中锁定 `wifi1` 的 `pad2pro`，曾将下一次启动切回旧内核。修复后的默认目标与
当前系统 profile 的 store 路径完全一致。启动菜单仍以 `nixos/current` 为默认，
当前代 `nixos-30b922b9be2bf74a6accde5c3e75b33f` 使用 `color1`。
日常更新时更新 `nixpkgs` 输入；所有内核包及模块聚合工具均随该输入更新。
已移除独立旧工具链输入及历史闭包路径断言，默认 `pad2pro` 也可因工具链更新重建内核。

```sh
sudo nixos-rebuild boot --flake path:/etc/nixos#pad2pro
```

`boot` 发布下一次启动代际；`switch` 同时切换服务，但当前运行内核直到重启才改变；
`test` 只暂时切换服务，不调用持久启动安装器。菜单默认项由共享 `boot.conf` 控制，
发布 NixOS 不擅自改变它。可以在 kShimC 中选择 NixOS 当前代际。

kShimC 启动项安装器读取每个代际的 Bootspec，安装实际 Image、完整 DTB、initrd，
命令行中的 `init=/nix/store/.../init` 精确对应这个系统。
从 2026-11-12 的载荷共享改动开始，新代际会按大小和 SHA-256 核对已有 NixOS
启动项。完整校验匹配的旧版本后，相同载荷在 `/boot` 内建立硬链接，不同载荷
才复制；新内核、新 DTB 或新 initrd 分别独立判断。每代的 manifest 和启动参数
仍独立保存，目录和文件格式遵循 kShimC 规范，没有软链接或 Nix store 路径载荷。

硬链接只在同一启动文件系统中创建，不跨到 `/nix/store`，也不共享其他发行版的
文件。安装器不原位修改或 chmod 已发布载荷；更新一律生成新文件。删除旧代际
目录不会破坏仍被其他代际引用的数据。旧的独立副本不做自动追溯合并。
空间预检只计算本次确实需要复制的字节，同时继续校验全部载荷及内存总量限制。
硬链接失败会中止发布并清理暂存目录，保留原菜单选择。
发布前建立 `/nix/var/nix/gcroots/kshim-nixos/<boot-id>`，使相应系统和模块闭包
不被 GC 删除。更新失败可能留下未引用但完整的版本和 GC root，宁可多保留，
不得误删旧入口。重试同一代际可恢复发布；不原位覆盖已有载荷。

`/boot` 默认以 `rw,noatime` 挂载，写入受 root 所有权及普通文件权限限制。
安装器验证 boot 的真实挂载点、ext4、GPT 标签、PARTUUID、FSROOT，然后发布并同步。
安装器保留原有挂载状态：通常保持可写；若用户手动设为只读，则仅在操作期间
临时改为可写，结束时恢复只读。不触碰 Android boot 分区。
菜单和 Nix profile 分属不同位置，不是一个跨文件系统的原子事务。

回退优先用 `nixos-rebuild boot --rollback` 更新系统 profile 并调用相同安装器，
或在菜单手动选择旧代际。菜单手选只改变当次启动，不写回系统 profile。
`nixos-rebuild switch --rollback` 会切换用户空间，但旧内核需重启才生效。

2026-11-12 直接只读计算实机整个 `boot_a` 的 SHA-256，结果为
`205ae86c8e9945808e5fb3f6356c16a8febc5c89acbbf9e1238d5fb6c583c402`，
与 `artifacts/nixos-pad2pro-menu-pagination-v3/boot.img` 完全一致，确认分页 v3
已安装。该版本取消固定 8 项上限，按需分页；本次检查时菜单仍为 8 项，未进行
超过 8 项的实机交互测试。旧版不支持超过 8 项的提醒不再代表当前安装版本。
读取证据保存在该材料目录的 `device-readback-20261112.json`，此检查不写设备。
启动项数量仍受 `entries.conf` 的 8192 字节限制；系统列表最多 4 个，载荷还受
启动分区空间及原有加载大小限制。每代保存独立启动路径，相同载荷共享磁盘数据。
**启动菜单现在通过声明式保留策略自动同步；系统 profile 仍由 Nix 管理。**
本机配置为：

```nix
boot.loader.kshim = {
  enable = true;
  configurationLimit = 5;
  cleanup = {
    enable = true;
    keepPrevious = true; # 默认值，保留一个启动回退
    keepVersions = [];  # 可填现有 boot identifier，固定额外救援项
  };
};
```

`configurationLimit` 默认 10，本机设为 5，按 system profile 的代际编号从新到旧选择，
`0` 表示所有尚存的 profile 代际，不表示保留已删除 profile 对应的所有历史菜单项。
菜单当前项、`/run/booted-system`、`/run/current-system`、system profile 指向的系统、
前一回退项、显式共享默认项和 `keepVersions` 固定项始终保留，因此实际数量可超过限制。
`keepPrevious = false` 可取消对前一代的额外保护，其他保护仍有效。

每次 `nixos-rebuild boot/switch` 发布启动项后执行同步；systemd 的
`kshim-cleanup.path` 监视 `/nix/var/nix/profiles`，因此手动运行
`sudo nix-collect-garbage -d` 删除 profile 后也会异步清理旧启动项。
按用户要求不设置定时检查，仅在发布启动项、profile 目录变化或手动调用时执行。
全新 `nixos-install` 目标尚无运行/激活系统链接时，安装钩子延后清理至后续 profile 变化或手动调用。
运行系统与激活系统不同也能清理，两者都受保护，无需为清理专门重启。

```sh
sudo nixos-kshim-cleanup --dry-run # 查看按当前声明式策略生成的保留/删除计划
sudo systemctl start kshim-cleanup.service # 立即同步并等待完成
journalctl -u kshim-cleanup.service
```

清理先校验分区 PARTUUID、菜单、GC roots、全部载荷哈希及 profile/runtime 快照，
在 `/var/lib/kshim/last-cleanup.json` 保存最近一次变更前的菜单和清单，
再原子更新菜单、删除无引用载荷、最后删除对应 GC roots；
`last-result.json` 记录完成结果。这些是元数据记录，不是被删除载荷的完整备份。
与安装器共用 `/run/lock/nixos-kshim.lock`，覆盖整个临时读写挂载周期。
出错时保留未完成的 roots，下一次检查可继续清理中断留下的文件/roots；
挂载结束恢复原有只读状态。共享菜单、Android 启动分区和其他系统不改动。

同步不删除系统 profile，不自动运行 store GC。GC 与 profile 监视器是异步的，
本轮 GC 可能仍看到旧的启动 GC roots；需要立即回收时可运行：

```sh
sudo nix-collect-garbage -d
sudo systemctl start kshim-cleanup.service
sudo nix-store --gc
```

回退 profile 若已由 `-d` 删除，`keepPrevious`/固定启动项仍有 GC root 可从菜单启动，
但不能再通过已删除的 profile 编号执行 `nixos-rebuild --rollback`。
`configurationLimit` 只限制启动菜单，不承诺释放仍被 profile 或其他 roots 引用的闭包。

2026-11-12 集成验证：78 项 Python 回归测试通过，完整 NixOS 构建和两次在线
`switch` 成功。新增第 33、34 代期间自动删除 9 个旧菜单项及其专用 roots，最终
保留最近 5 个 profile 代际和额外保护的已启动系统，共 6 项。当前系统为
`vnfmfvcknilg0njn4lsqc1yf7nasciv1`，启动标识为
`nixos-422dae7ad0f6578043ceb31875781408`；运行中的旧启动系统仍受保护。
实机目录变动触发 path 服务成功，重复清理和 dry-run 均无待删项，path
为 active，服务结果为 success，失败服务为 0，`/boot` 恢复 ro。
内核 Image 仍指向已验证的 `hdygs3c45sfmribpg42x4i3cwplk61gs` 输出。
本轮没有重启，也没有执行 store GC；启动菜单的实机交互仍待下次启动验证。

原手动清理工具
`tools/prune-kshim-boot.py` 接受经过核对的 JSON 计划，要求实际菜单、运行系统、
系统 profile、GC roots 和每个载荷的哈希符合预期。它在 `/boot` 外备份菜单和清单，
先原子更新当前/前一代选择，再删除计划内的旧载荷和对应 GC root；保留明确指定的
普通回退版；计划的可选 `retain` 列表还能保留文本维护系统等额外回退项。
需要明确只保留当前代时，计划可设 `previous=none`；该路径有独立回归测试。
拒绝删除共享菜单的显式默认项。结束时恢复原有只读挂载。

此工具只清理 `/boot`，保留 Nix 系统 profile 历史，不运行 store GC。
旧 profile 仍可能保留旧系统闭包；仅隐藏菜单项则连 `/boot` 空间也不会释放。
`nix-collect-garbage -d` 会删除旧 profile；需要保留 profile 回退能力时应改用按时间删除的策略。
清理测试覆盖损坏载荷、菜单变更、默认项保护、目录符号链接和删除故障。

kShimC 没有启动失败计数和自动回退。ext4 journal 损坏时需要独立维护环境修复；
旧菜单项不能解决 `/boot` 本身不可读取的问题。

## wifi1 内核更新（2026-11-11）

`nixos-7d5488900107d53c387d23c300031c25` 已通过标准 `boot` 安装钩子发布为
current，内核为 `7.2.15-nixos-erhai-870167fad062-wifi1`。
previous 为原 current `nixos-c5d389974e65db7114fa0e40fa2ff8e0`，同时保留
v6 普通版 `nixos-711a16405621b34c4e0809e735fa0d98`。三套目录和 GC roots 均在。

系统 profile 指向新系统，实机清单和三份载荷的摘要与构建产物匹配；原有两个
代际的载荷均保留，启动分区恢复只读，使用约 246 MiB、剩余约 661 MiB。
原配置和整个 kShimC 文件树的备份在
`/var/lib/pad2pro-updates/wifi1-7d548890/`；电脑端材料为
`artifacts/nixos-pad2pro-wifi1/`，其中 `installation.json` 是实机发布验证记录。

安装操作没有主动重启或切换运行服务。用户随后重启进入新代际，已通过 SSH 确认
实际运行 `-wifi1` 内核与对应闭包，5 GHz 目标热点的扫描、关联和联网通过。
USB 管理链路曾短暂不可达，现已恢复并验证 SSH、双向 ping 和数据传输；
旧版本仍可从 previous 手选启动。实机验证及 USB 事件详见 `WIFI.md`。

## wifi1 更新前的实机代际记录

更新前的普通版为 `nixos-c5d389974e65db7114fa0e40fa2ff8e0`；清理后的前一代为
已验证的 v6 普通版 `nixos-711a16405621b34c4e0809e735fa0d98`。
此前 v7 普通版和诊断版均已从持久菜单启动。诊断代实测 CPS8601 修复模块、固件版本、
运行时挂载和 0 个失败服务；普通当前代已确认登录提示、USB NCM 与 SSH 主机身份，
HTTP 诊断按配置关闭；`nixos` 密码已由用户交互设置并通过 SSH 登录验证，root 保持锁定。

v6 基线已经完成菜单手选回退和真实 GC 测试：只删除无引用 canary，四个保留代际
的递归闭包仍完整，且在 GC 后启动。升级 v7 后曾保留六个代际，实际 GC roots 与
全量 store 内容已核对，清理前六个启动条目均通过独立读取器。
随后按用户要求删除四个旧启动目录及对应 GC roots，仅保留上述两个普通版；
实际 `/boot` 占用从约 487 MiB 降至 164 MiB，释放约 323 MiB，并恢复只读挂载。
保留载荷通过完整哈希检查；系统 profile 历史仍保留，本次未运行 store GC 或重新启动。
失败发布、菜单容量限制和 GC root 保留已有主机测试；断电故障注入与
`nixos-rebuild switch --rollback` 尚未实测。

当前 `pad2pro` 在 ARM64 平板原生构建内核，日常更新不需要 x86 构建机；
显式候选 `pad2pro-build` 在电脑交叉编译内核。两者统一使用当前 `nixpkgs` 的
官方内核、设备补丁集和工具链。
不再以历史闭包路径断言固定旧产物。
具体源码、配置和补丁的边界见 [内核源码与维护](history/KERNEL-SOURCE.md)。

Android 数据区经原厂 recovery 重建后，已验证从 Android 经持久菜单进入 NixOS
前一代，再从一级菜单返回 Android。日常使用请选择普通“当前代 / Current”
`c5d38997…`；前一代 `711a1640…` 同样是普通版，默认关闭 HTTP 诊断。
