# 有线快充与 GNOME 功率显示

## 移植范围

当前内核 `7.3.4-erhai-p6` 将参考项目 0.10.2 的充电实现前移到本项目的 Linux 7.3。
参考内核提交为 `dc8c28c12761bcc3a9b320931d6d12476ae91192`，桌面源码提交为
`b2b06a3aa082d76645f199f7c0f76591f6d9b5cc`。两者仅为来源信息：内核修改由独立
`linux-sm8750-erhai-patchset` 导出，桌面源码保存在 `packages/charging/`，正常构建
不访问参考项目工作区。

- SUPERVOOC、UFCS、PPS 共用充电通路仲裁及 SC8547A 双电荷泵；兼容的固定 PD／QC
  充电器可请求 9 V，失败时回退普通充电。
- 电芯温度、连接器温度、电压、电流、适配器及线缆能力共同限制功率。保留原厂
  曲线、高电量接入、降流、低电流充满、buck FFC 尾段和再充电处理。
- 电芯快充表覆盖 0°C 至低于 51°C；这不表示处于该区间就必然启用电荷泵。
  连接器温度未通过检测、传感器失败或充电器不兼容时，控制器仍会拒绝或退出快充。
- 继续尊重 GNOME 的充电保护选择和标准限充阈值。启用 80% 保护时会按该阈值停充；
  “充满电量”模式才允许充到 100%，本次移植不清除用户的选择。

硬件控制留在内核。桌面程序只读取标准电源属性和 `charge_contract`，不写电流、
电压或电荷泵寄存器。缺少可选 UFCS 认证固件时，沿用参考实现的未认证电流上限，
不要求导入身份数据或从 Android 提取密钥。

## Android 与 NixOS 电量口径

2026-11-17 已实测 Android 恢复陈旧的 `shutdown_soc=100`，而原始 SOC 为 87%；
其后还会按 UI 满电定时器上报 Full，实际仍有充电电流。已核对的 NixOS p6 正常／FFC
阈值与本机原厂实时设备树一致。结论、读数与边界见 [电量差异排查](BATTERY-SOC.md)。

## 桌面行为

从 p9 起，接电时顶栏充电菜单提供「暂停充电」。开关通过板载电池的
`charge_behaviour` 把请求交给内核，保留现有充电阈值。平板负载超过充电器
可提供的功率时，电池仍可能放电。选择保存在平板本地，下次开机自动恢复。

`modules/charging.nix` 安装适配当前 GNOME Shell 版本的
`charge-indicator@tablet-linux` 扩展，并通过系统 dconf 提供启用默认值。
已有个人扩展选择继续生效；若此前自行设置过扩展列表，可在 GNOME 扩展管理器中
启用 **Tablet Charging Power**。

顶栏显示电池侧净功率和当前通路；菜单另列输入电压／电流、电芯电压、温度、协商值
及退出原因。SUPERVOOC 暂停普通 buck 通路时，输入读数取双电荷泵的实测总电流，
避免固件 buck 电流为零时显示错误；不以请求值冒充实测值。电池净功率为电池电压乘以有符号电流：系统消耗已体现在该值中，
它不等于充电器铭牌功率，也不等于 USB 输入功率。缺失的测量显示未知；负值表示
电池净放电。

接着有线充电器时，内核保持 `qcom-battmgr-charge` 唤醒源，GNOME 用户服务
`tablet-charge-idle` 仅抑制休眠，允许锁屏和屏幕关闭。合盖在外部电源上执行锁屏。
充满或达到限充阈值后，只要充电器仍连接，系统继续保持唤醒；拔线后释放抑制。
电脑 SDP／CDP 口和对外供电角色不属于该接充电器保活策略。

系统为空闲休眠提供 15 分钟默认值；已有个人电源设置继续生效。电池供电时合盖恢复
正常休眠。登录界面和显式休眠请求仍受内核充电状态保护。

## 构建与检查

```sh
nix build .#charging-desktop
nix build .#checks.x86_64-linux.charging-objects
nix build .#checks.x86_64-linux.patchset-replay .#checks.x86_64-linux.device-regression
nix build .#checks.x86_64-linux.boot-publication
nix build .#nixosConfigurations.pad2pro-build.config.system.build.toplevel -L
```

最终内核配置必须包含 `CHARGER_SC8547A=y`、`CHARGER_ERHAI_PPS=y` 和
`OPLUS_UFCS_CLASS=y`。最终 DTB 检查同时核对双泵、两个 Gen4 连接器温度通道、
原有 ADSP 专用堆和 1.896 V VDDIO 约束。仅有新增驱动文件不能代表这些依赖已接通。

桌面回归覆盖电池净功率、负电流、缺失读数、协议识别和插拔时的休眠抑制生命周期。
内核纯策略测试直接编译实际板级头文件，覆盖温度／SOC 边界、高 SOC 接入、曲线
降流、低电流充满、过压恢复和再充电。它们不能替代充电器与实机的协议验收。

## 实机验收状态

2026-11-16 在本机 OPD2413 和 VCBAOBCH 上完成以下验证：

- p6 正常启动，内核 taint 为 0，无失败的系统服务。完整交叉内核、模块、BTF、
  原生 ARM64 用户空间及启动树构建成功，108 项项目回归通过。
  重复启动的原生内核构建已取消，未计为原生内核构建成功。
- 89% 电量进入 SUPERVOOC，双泵工作；初始输入约 9.27 V／2.48 A，电池净充电
  约 17.5 W。旧 p5 同一充电器的基线约为 5.25 V／1.99 A、净充电 5.2 W。
  这些是采样值，不是保证功率。
- 锁屏灭屏连续约 87 秒的 44 个采样均保持 SUPERVOOC 和双泵，电池净充电
  6.7–17.2 W；充电唤醒源持续活动，休眠成功计数保持为 0。
  GNOME 抑制项为 `tablet-charge-idle`，仅设置 suspend 标志 4。
- 接近充满时以 `low-current-full` 正常退出 SUPERVOOC，转 QC 9 V 和 buck FFC
  两级补电，最终 `status=Full`、`buck_phase=5`、`buck_full=1`、`buck_enable=0`。
  传感器有效，充电／电量计错误均为 0。
- 真正充满后连续 65 秒的 14 个采样均保持 Full，充电唤醒源活动，USB 在线，
  桌面助手返回 `inhibit`，休眠计数不增加。

最终配置已完成普通重启，启动／当前／系统 profile 均指向同一最终系统。
用户正常登录后，新版 GNOME 扩展为 ACTIVE，拔线时助手为 `allow`，会话无充电
抑制项。拔线后 `qcom-battmgr-charge` 活动时间为 0。

休眠测试有一项环境限制：前两次因 LocalSearch 索引任务卡在 FUSE lookup/stat
而在冻结阶段失败（`freeze/-16`）；当时 Connect2 SSHFS、portal 和 GVFS 挂载存在。
临时停止索引后，`rtcwake -m mem -s 20` 成功，实际休眠约 20.01 秒，休眠成功计数
从 0 增至 1，随后已恢复索引服务。因此充电保活释放和隔离后的休眠／唤醒已验证，
含该 FUSE 索引活动的完整桌面会话仍不能标记为休眠通过；本次没有修改个人索引设置。

重插时电量 99%，重新进入 SUPERVOOC，输入约 9.25 V／2.04 A、电池净充电约
12.6 W。随后约 38 秒的 20 个采样均保持双泵和 SUPERVOOC，收发错误均为 0，
退出计数未增加，充电唤醒源及 GNOME suspend 抑制项恢复。新版扩展使用实测泵电流。

上述休眠／重插测试后，约 16:02 Wi-Fi SSH 再次失联，屏幕和网络状态待确认；
不能从 SSH 不通单独推断休眠、充电或内核故障。任务恢复时（约 21:25）SSH 已可用，
但设备已是另一次启动及较后的系统配置；该启动仍使用相同 p6 内核和充电桌面包，
SUPERVOOC／扩展正常。该启动还记录了一次成功休眠和一次接电时被内核拒绝的
休眠请求（之前冻结 user.slice 超时）；不能据此解释 16:02 的历史失联。UFCS、PPS、独立固定 PD／QC
充电器和磁吸盖／键盘保护套未做实测；QC 9 V 仅在本次 VCBAOBCH 尾段观测到。
没有保护套时，以锁屏灭屏测试对应实际使用场景。

当前系统通过标准 `nixos-rebuild switch` 安装，p5 启动项保留作为回退。
完整的分项结果与范围见补丁集 `provenance/charging-p6-device-acceptance.json`；
内核来源和构建证据见 `provenance/charging-0.10.2-port.json` 及对应构建报告。
桌面原始摘要和本地读数修正见 `packages/charging/upstream-source.json`。
