# 官方内核与 Erhai 补丁集

2026-11-14 已完成迁移，日常内核为 nixpkgs 官方 Linux **7.3.4** 加独立设备补丁集，
标识 `7.3.4-erhai-p5`，共 23 个补丁。完整交叉与平板 ARM64 原生系统均已构建并校验。
原生冷启动、默认 current 普通重启、显示／触控／GPU／扬声器／Wi-Fi／蓝牙／充电和
RTC 休眠恢复通过；8 核在线、taint=0。2 GiB 并发 THP 四轮分配与读回通过，累计写入 8 GiB。

平板 `/etc/nixos` 已安装对应声明式配置，标准
`nixos-rebuild switch --flake /etc/nixos#pad2pro` 及再次激活通过。
原账户的 UID/GID、密码、家目录及所有者、附属组和 subuid/subgid 均保留，重启后可登录。
系统不声明普通账户，不绑定个人用户名。安装备份位于
`/var/lib/erhai-patchset/20261114-130657-final-install/`。

`current` 指向最新发布的系统代际，`previous` 指向前一代；保留数量由 kShimC 清理配置管理。
历史旧内核只作故障恢复，不新增适配。按用户选择，`/boot` 默认以 `rw,noatime` 挂载，
发布／清理工具保留原有挂载模式；两个入口的完整载荷与 GC roots 已核验。

## 构建关系

独立项目为 `linux-sm8750-erhai-patchset`，维护来源为官方 stable 基线上的 Git 分支
`patchset-7.3`。补丁与硬件配置由提交导出为 series、patches 和 manifest；本项目的
`inputs/kernel-patchset` 只能由同步工具生成。安装导出包含 `inputs/` 的发布快照及随 Git 提供的通用 OEM
固件归档，平板构建不需要电脑上的旧 fork 或开发仓库路径。

`packages/kernel.nix` 复用 nixpkgs `linux_7_3`。硬件模块通过 `boot.kernelPatches` 和
`structuredExtraConfig` 追加设备补丁与配置；先对正式源码打补丁，再生成最终 `.config`。
保留 defconfig、硬件片段和本项目 `packages/nixos.config` 的配置语义，最终启用／禁用
请求必须通过检查。DTB、模块、initrd 与 Bootspec 都引用最终 `config.boot.kernelPackages.kernel`。
CPS8601 修复已进入补丁集，不再注入重复的模块覆盖路径。

`pad2pro` 在平板原生构建内核；`pad2pro-build` 在电脑交叉编译内核，ARM 用户空间步骤
需要 ARM builder 或仿真。两者统一使用当前 nixpkgs 工具链，不保留旧编译器或历史闭包门禁。
设备补丁以 `--fuzz=0` 独立重放，编译源码逐文件核对重放结果；失败不得跳过。

## 更新与验证

在平板更新同系列正式版及工具链：

```sh
cd /etc/nixos
run0 nix flake update nixpkgs
run0 nixos-rebuild switch --flake /etc/nixos#pad2pro
```

升级前先完成补丁重放、配置、完整系统构建和候选实机验收，再提升默认。
需要修复补丁时，在独立项目修改 Git 提交并导出／验证，然后同步：

```sh
python3 tools/vendor-kernel-patchset.py /absolute/path/linux-sm8750-erhai-patchset
nix build .#checks.x86_64-linux.patchset-replay .#checks.x86_64-linux.device-regression
nix build .#checks.x86_64-linux.wifi-firmware .#checks.x86_64-linux.cps8601-firmware
nix build .#checks.x86_64-linux.boot-publication
nix build .#nixosConfigurations.pad2pro-build.config.system.build.toplevel -L
```

已实际完成 7.3.3 → 7.3.4 前移：删除上游已合入的修改，处理 stable 语义变化后重放、
构建并实机验收。下一系列先移植补丁，再修改包选择及 manifest；禁止改选较旧内核绕过失败。

## 验收与修复记录

- 正式源码重放与来源：`provenance/replay-7.3.4-p5.json`、`forward-7.3.4.json`。
- 完整原生系统、模块、BTF、最终 DTB／initrd 与固件：`full-native-system-p5-validation.json`。
- 原生设备验收与日常安装／重复激活／重启：`native-p5-device-acceptance.json`、`daily-p5-installation.json`。
- 面板首次上屏重启：VDDIO 固定为 1.896 V，见 `panel-vddio-diagnosis.json`。
  Android 原厂消费端请求、初始化值和亮屏驱动报告均为 1.900 V；1.896 V 是当前主线
  8 mV 模型的下方相邻档位，非原厂精确电压。对照和因果边界见 `android-factory-vddio-reference.md`。
- 蓝牙无法开启：修复 UART 关闭路径重复禁用 IRQ，见 `uart-irq-balance-diagnosis.json`。
- 内存负载中止：ADSP 的 12 MiB 堆改为专用 no-map 保留区，见 `adsp-heap-native-fault.json`。
  内核安装阶段必检实际 DTB，实机 memblock 已确认不与 System RAM 重叠。

以上 provenance 文件位于独立补丁项目及本项目 `inputs/kernel-patchset`。
历史闭包、哈希及失败尝试用于追溯，不作为以后固定工具链或旧构建产物的门禁。
