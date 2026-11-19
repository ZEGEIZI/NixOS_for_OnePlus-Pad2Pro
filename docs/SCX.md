# SCX 使用说明

`modules/scx.nix` 通过 NixOS 的 `services.scx-loader` 声明式安装并启动管理服务，
同时安装 `scxtui`、`scxctl`、调度器、D-Bus 接口与 polkit 策略。
`scx.full` 本身只提供调度器和 `scxtop`，不包含 `scxtui` 或管理服务。
内核提供 sched_ext/BTF 支持。

开机只启动管理服务，不自动选择调度器；`default_sched = null`。
同时显式设置 `default_mode = "Auto"`，避免仅设置空默认调度器时生成空 TOML，
导致 scx-loader 1.1.3 报 `The config file is empty!`。
在终端运行 `scxtui` 可查看并切换调度器，普通桌面用户执行管理操作时由 polkit
要求管理员认证。需要从 SSH 管理时可使用 root，或 `sudo scxtui`。
也可以通过命令管理：

```sh
scxctl list
scxctl get
sudo scxctl start --sched lavd --mode powersave
sudo scxctl stop
```

停止后内核恢复默认调度。可通过 `cat /sys/kernel/sched_ext/state` 检查当前是否启用，
通过 `systemctl status scx_loader` 和 `journalctl -u scx_loader` 检查管理服务。
通过界面或命令所做的运行时选择不会写回 NixOS 声明；重启管理服务或系统后恢复未选择状态。

## 2026-11-14 scxtui 实机验证

- 内核 `7.3.4-erhai-p5`，scx-loader `1.1.3`，调度器 `1.1.4`。
- 已在平板通过 `nixos-rebuild switch` 激活；`scx_loader.service` 已启用且运行。
- SSH 终端实际打开 `scxtui`，通过 D-Bus 列出 14 个受管理的调度器。
- 在界面中启动 LAVD PowerSave、切换 LowLatency、停止；运行时内核状态为
  `enabled`，ops 为 `lavd_1.1.4_aarch64_unknown_linux_gnu`。
- 测试后停止调度器，保留管理服务；默认调度器未配置。
- 仓库 `nix flake check --no-build` 通过；实机账户数据库及附属 UID/GID 范围未改变。

以下为先前启用默认调度器时的历史验证记录，不代表当前运行状态。

## 2026-11-13 实机验证

已用当前 nixpkgs 的 GCC 16.2.0 完整构建内核、模块及匹配的 CPS8601 模块，
通过 `nixos-rebuild boot` 发布并按用户授权重启。
日常 `pad2pro` 与 `pad2pro-build` 均选择当前启用 BTF/sched_ext 的 `kernel` 包。
外置 CPS8601 模块在 fixup 后由当前 `kmodigest` 生成摘要证书，兼容当前模块聚合流程。

- 运行内核：`7.2.15-nixos-erhai-efc39b9d9726-upstream4-ebpf1`。
- `/sys/kernel/sched_ext/state` 为 `enabled`，ops 为 `lavd_1.1.4_aarch64_unknown_linux_gnu`。
- `scxctl get` 返回 `running Lavd in PowerSave mode`，进程参数为 `scx_lavd --powersave`。
- 运行、已启动和系统 profile 均指向发布的 `dndi6vrx4pgbv5lsbcki6zjszh53zgkc` 系统。
- 图形、网络、蓝牙服务 active，蓝牙控制器和 CPS8601 模块存在，失败服务为 0。
- 78 项 Python 回归测试通过；新内核、模块、外置模块证书、完整系统和 initrd 构建通过，
  `/boot` 恢复只读。用户确认已进入 GNOME 桌面或登录界面。

原始运行结果见 [SCX-VALIDATION.json](SCX-VALIDATION.json)。本轮确认配置和运行状态，未测量实际功耗收益。
