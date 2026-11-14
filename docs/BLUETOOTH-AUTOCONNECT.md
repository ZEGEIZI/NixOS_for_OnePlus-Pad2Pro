# 蓝牙开机自动连接

2026-11-12 已修复。FIIO BTR13 保持开机时，平板正常重启、登录 GNOME 后
自动连接并成为默认 A2DP/LDAC 输出。用户明确确认没有手动点连接，播放正常。
实现与实机状态见 [验证清单](BLUETOOTH-AUTOCONNECT-VALIDATION.json)。

## 原因

原厂固件切换解决的是控制器初始化、UART 与固件加载；它不负责桌面的连接策略。
此前将固件切换当作结束条件，自动连接未通过后过早收尾，遗漏了这一层配置。

实机的 FIIO 已 Paired/Bonded/Trusted，适配器 Powered，BlueZ `AutoEnable=true`。
但 BlueZ 5.87 的 AutoEnable 只开启适配器；`plugins/policy.c` 的重连逻辑主要在
链路超时和挂起恢复时触发，不负责启动时主动连接所有已配对音频设备。

当前 PipeWire 1.6.11 的 `spa/plugins/bluez5/bluez5-dbus.c` 将
`DEFAULT_RECONNECT_PROFILES` 设为 `SPA_BT_PROFILE_NULL`。
`bluez5-device.c` 只有收到 `bluez5.auto-connect` 配置后才设置启动重连的 profile。
原配置没有设置它，所以声卡和配对可用仍不足以保证登录后主动连耳机。

## 修复

`modules/bluetooth.nix` 给 WirePlumber 添加通用规则：

```nix
"monitor.bluez.rules" = [{
  matches = [{ "device.name" = "~bluez_card.*"; }];
  actions.update-props."bluez5.auto-connect" = [ "a2dp_sink" ];
}];
```

规则在蓝牙和 PipeWire 启用时生效。由活动会话的原生音频监视器发起 A2DP
连接，沿用上游的启动状态机和 profile 就绪处理。原生代码仅对已配对、
受信任且未被屏蔽的设备执行连接；配置不包含设备地址，不改变信任状态。
这次针对音乐播放启用 A2DP，没有增加自定义守护进程或轮询脚本。

接收器需要开机且可连接。原生启动尝试失败后不提供无限轮询；本次实际遇到过
接收器不可达的 `Host is down`，重新开机并重新启动音频监视器后自动连接成功。
本次验收的是接收器已开启时的会话启动和整机重启自动连接。

## 验证

1. 配置前复现：Paired/Trusted 为 yes，Connected 为 no，启动后没有 A2DP 输出。
2. 配置启用时，在系统 D-Bus 上捕获到原生 `ConnectProfile` 请求，UUID 为 A2DP Sink；
   首次接收器不可达，返回 `Host is down`，没有把配置加载成功误记为连接成功。
3. 用户重新开启 FIIO 后，只重启 WirePlumber，未调用手动连接命令；FIIO 自动连接，
   默认输出和 A2DP/LDAC 均实际读回成功。
4. 正常重启新系统，boot ID 改变，GNOME 活动会话的 FIIO 已连接并为默认输出；
   用户确认没有手动连接，播放正常。
5. 完整系统构建、在线 test/switch、启动载荷核验通过；冻结 brahma1 内核、模块、
   DTB、initrd 均沿用原值。系统与用户失败服务为 0，Wi-Fi 和内置音频枚举正常。

系统：`/nix/store/wffzawniq22s875dh2snxn0pa1618zgd-nixos-system-pad2pro-26.11.20261107.f4a03c0`。
启动代际：`nixos-7c5d9bdd25f14bba4832f2cd2cdfd562`。
设备上的构建与激活日志：`/var/lib/pad2pro-updates/bluetooth-autoconnect/`。
遵照用户要求，本轮没有创建备份。
