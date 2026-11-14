# SCX 使用说明

按用户要求，当前配置已移除 `scx_lavd + PowerSave` 的声明式服务设置，
不再导入 `modules/scx.nix`，不生成 `scx_loader.toml`，不开机自动启动调度器。
SCX 调度器工具仍通过 `environment.systemPackages` 安装，内核仍提供 sched_ext/BTF 支持。

需要时可手动启动：

```sh
sudo scx_lavd --powersave
```

在该终端按 Ctrl+C 可停止；停止后内核恢复默认调度。
可通过 `cat /sys/kernel/sched_ext/state` 检查当前是否启用。

以下为先前启用时的历史验证记录，不代表当前运行状态。

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
