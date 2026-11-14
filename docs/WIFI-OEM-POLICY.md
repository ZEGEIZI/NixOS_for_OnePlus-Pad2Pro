# 原厂 WLAN 频段策略适配

2026-11-12，保留已验收的 upstream3 闭包作回退，针对关联扫描约 20 秒被取消做对照。
脱敏数据见 [调查与验收记录](WIFI-OEM-POLICY.json)。

## 取消发起方已确认

临时开启 supplicant 调试日志并保持 `DebugShowKeys=false`，同时采集驱动记录。
日志明确显示：

```text
Scan requested (ret=0) - scan timeout 20 seconds
nl80211: Scan timeout - try to abort it
nl80211: Abort scan
```

因此此前的取消由 wpa_supplicant 的 nl80211 后端主动发起；当时驱动仍在执行后面的
6 GHz 批次。随后通过同一个 supplicant 的 D-Bus Scan 接口，只指定当前可用的
36 个 2.4/5 GHz 信道，正常完成记录为 9.197264 秒。该对照支持缩小错误暴露的频段，
最终仍需用新内核下 NetworkManager 的普通扫描验证，不能仅凭定向请求判定修复成功。
调试结束后恢复原日志等级和 `ath12k.debug_mask=0`。

## 原厂配置含义已查明

本机 Android 实际加载的 persist 配置有 `BandCapability=3`。
一加公开 Android 16 Pad 2 Pro 分支
`oneplus/sm8750_b_16.0.0_pad_2_pro` 的固定提交
`cc463675855afb8702a263f415330a240f5cd919`，在
[cfg_mlme_generic.h 第 451 行](https://github.com/OnePlusOSS/android_kernel_modules_and_devicetree_oneplus_sm8750/blob/cc463675855afb8702a263f415330a240f5cd919/vendor/qcom/opensource/wlan/qcacld-3.0/components/mlme/dispatcher/inc/cfg_mlme_generic.h#L451)
明确说明 `3: Both 2.4G and 5G`。这也与 Android 实际公布的 STA 信道列表一致。
该公开分支用于确认设置语义，不声称其提交就是当前 Android 二进制的精确构建提交。

## 当前候选的实现

共享内核提交 `efc39b9d972665c270adc4e4ec2c46685792ffda`：

- OPD2413 WLAN 设备树采用标准 `ieee80211-freq-limit`，表达原厂 2.4/5 GHz 配置。
- ath12k 在私有信道数组准备好、wiphy 注册前调用 `wiphy_read_of_freq_limits()`。
- 注册时将禁用状态保存到 `orig_flags`，后续固件自管理监管更新仍保留板级限制。
- 没有该设备树属性的其他设备继续使用原有信道集合。

它不修改固件或国家码，不把自管理 PHY 的 `US` 强制改成 `CN`，也不改变已验证的
分范围扫描路径。此限制对应原厂出货配置，不用于断言 WCN7860 芯片不支持 6 GHz。

相关 ARM64 对象与板级 DTB 编译无警告，绑定文档及编译后 DTB 的 ath12k schema
检查通过。回归检查运行实际 cfg80211 频率过滤与监管更新函数，覆盖边界信道、保留已有
禁用状态、私有数组隔离，以及更宽监管规则不能重新开启受限信道。原范围扫描故障路径
检查也通过。完整候选版本为 `7.2.15-nixos-erhai-efc39b9d9726-upstream4`，已完成实机验收并设为日常基线。

## 验收条件与挂起观察

实机运行确认版本为 upstream4，自动连接目标 5200 MHz；首次只读观测在开机
56.54 秒，不能据此计算精确连接耗时。实际可用信道为 36 个，所有 6 GHz 信道禁用。

两次未限定 SSID／频率的 NetworkManager 普通全频扫描均正常完成，supplicant 记录
9.581323／9.806365 秒，没有再触发 20 秒超时。两轮分别 100 次网关 ping 全部成功，
连接保持 5200 MHz，无新驱动错误。用户确认显示、触控、音频和蓝牙正常；按用户要求，
确认后停止重复音频和蓝牙测试，没有将采样状态等同于持续音频质量监测。

完成一次实际 s2idle 挂起恢复：成功计数 0→1，内核日志确认进入／退出挂起。
RTC 预设 30 秒，33.09 秒墙钟时间后观察到恢复，约 5.11 秒后已关联 5200 MHz
并成功访问网关，随后 HTTPS 通过，6 GHz 信道仍全部禁用。计时是观察上界；
没有单独确认唤醒 IRQ 源。恢复后无失败服务或新 ath12k／严重内核错误。

日常包独立固定为 `upstream4-kernel`，配置为 `docs/history/kernel/configs/upstream4.config`，
完整系统及内核闭包与实测版本一致。共享启动分区的 Image、DTB、initrd 摘要逐项与该系统
核对一致；保留 upstream3 为 previous，brahma1 也保留。本轮没有重复普通重启，
断电冷启动、deep sleep 和长时间运行仍未验收。

第一次 baseline RTC 挂起观察脚本把 `systemctl suspend` 的异步返回误当成恢复，
提前清除了闹钟，结果已作废。用户手动唤醒后，旧日常内核仍关联 5200 MHz，无失败服务。
后续观察改为等待 `/sys/power/suspend_stats/success` 实际增加后才检查重连或清理闹钟，
不把命令已返回或进入挂起前的连接状态当作恢复验收通过。
