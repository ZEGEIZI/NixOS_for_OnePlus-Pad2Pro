# Android 与 NixOS 电量差异排查

2026-11-17 在 OPD2413 上复现。此次 100% 对 87% 的主要原因已经由 Android 启动日志
确认：Android 恢复了旧的关机界面电量，而 NixOS 显示电量计／固件报告的 SOC。
此次采样没有发现 NixOS 电压单位错误或高于原厂的已核对充电阈值；不能仅凭百分比
差异认定过充。没有修改充电参数、电量计、校准数据或 Android 的电池状态。

## 实机证据

| 阶段 | 显示／上报电量 | 原始电量 | 电池电压 | 充电状态 |
| --- | --- | --- | --- | --- |
| 切换前 NixOS，22:59:45 | 87% | 固件 SOC 87% | 4.301712 V | 未接电，净放电约 0.180 A |
| Android 启动日志 | 初始化为 100% | `soc=87`，平滑值 88 | 启动日志未同帧记录 | 恢复 `shutdown_soc=100` |
| Android 23:04:15 | `ui_soc=100` | `batt_soc=89`，平滑值 90 | 日志 4.338 V；即时 gauge 4.341 V | `batt_full=0`，仍充电 |
| Android 约启动后 305 秒 | 100%，随后上报 Full | `soc=90` | 相邻日志约 4.342 V | 界面满电定时器到期 |
| Android 23:08:42 | 服务 `level=100,status=5` | `batt_soc=91`，平滑值 92 | 日志 4.348 V；即时 gauge 4.352 V | 仍有约 0.96 A 充电电流 |

Android 的原厂日志使用负电流表示充电，`ibat_ma` 单位是 mA；NixOS 的标准
`current_now` 使用 µA，已反转为正值充电。不要直接比较未经单位、符号转换的两个字段。
切换时外部供电从未接电变成 USB CDP，且采样不是同时进行；几十 mV 的差别不能用来
推断 ADC 校准偏差，但这些读数没有串并联导致的两倍差异或 mV／µV 千倍差异。

Android 的四条关键日志为：

```text
shutdown_soc=100, soc=87, partition_uisoc=-22, smooth_soc=88
set the init ui_soc = 100
pre set battery full soc=90 timeout=300s
batt_full=true
```

这不仅解释了百分比差异，也说明 Android 此次的“Full”并不等同于电流已截止。
同一阶段 `battery_log_content` 的 `ibat_ma=-960`、`fv_mv=4490`，电池仍处于补电中。
原始充电计数和电量计读数另见[结构化证据](evidence/battery-soc-20261117.json)。

## 实现路径

NixOS p6 的 `qcom_battmgr.c` 接收 `BATT_CAPACITY`，除以 100 后直接导出
`POWER_SUPPLY_PROP_CAPACITY`。这是固件的 SOC 路径，没有 Oplus 的关机 UI 电量恢复层。
整数取整最多造成不足 1 个百分点的差异，解释不了本次 13 个百分点的差异。

OnePlus 公开源码 `cc463675855a` 的
`vendor/oplus/kernel/charger/v2/oplus_chg_comm.c` 包含与实机日志相符的行为：

- 启动时读取 `shutdown_soc`；与原始 SOC 相差小于 20 时，可以将它直接作为 `ui_soc`。
  本次保存的 100 与原始 87 相差 13，因此初始化为 100。
- `ui_soc`、`smooth_soc`、原始 `soc` 是独立状态，并非简单固定比例换算。
- 满足条件时，UI 100% 持续 `batt_full_time` 后调用 `oplus_comm_set_batt_full` 提前
  上报满电。实机设备树的该时间为 300 秒，且实机日志确实在约 305 秒执行了该路径。
  真正的软件／硬件截止判定与该 UI 上报路径是不同的逻辑。
- FFC 前的满电提前判断使用原始 `chip->soc == 100`，不是 `ui_soc == 100`。
  NixOS 的对应判断也使用原始 SOC；本次未发现这里因 UI 差异额外提高截止电压。

公开源码仅用于解释实机日志，不宣称该提交就是运行中 Android 内核的精确源码版本。
双系统中保存的 Android UI 电量可能落后于 NixOS 期间的真实耗电；本次已实证恢复了
陈旧的 100，但没有进一步改写持久化数据来测试保存电量的更新机制。

## 与正在运行的 Android 设备树比较

读取的是这台平板当前启动的 `/sys/firmware/devicetree/base/soc/oplus,comm`，
并非仅比较历史源码默认值。以下表格为正常温度、零老化降压时的关键参数：

| 参数 | 原厂 Android 实时 DT／状态 | NixOS p6 |
| --- | --- | --- |
| 普通充电 FV | 4490 mV | 4490 mV |
| 普通软件满电电压／电流条件 | 4440 mV／597 mA | 4440 mV／597 mA |
| FFC 请求 FV | 4630 mV | 4630 mV |
| FFC 换步／结束电压条件 | 4540 mV | 4540 mV |
| FFC 两级电流 | 1500、1000 mA | 1500、1000 mA |
| FFC 两级截止电流条件 | 1300、900 mA | 1300、900 mA |
| FFC 前满电电压条件 | 4485 mV，另需原始 SOC 100 | 相同 |
| 电池过压判定 | 4600 mV | 4600 mV |

完整温区数组、再充电电压等共 10 项已核对数据在结构化证据中。FV 是控制请求，
不等同于电池实际达到的电压；特别是不能从 NixOS 的 `voltage_max=4630000` 推断
电池已经充到 4.63 V，FFC 仍有单独的换步／结束条件和过压判定。

本次普通 USB CDP 充电未覆盖新的 SUPERVOOC／UFCS／PPS 全周期终止测试，也没有
外接仪表同时校验两边 ADC。因此结论是“已解释此次电量差异，未发现已核对阈值
高于原厂”，不是对所有充电工况作全面安全保证。后续若需比较真正的物理充满点，
应比较同一充电器、相近温度下的电芯电压、净电流、控制器截止标志和协议状态，
不要以界面达到 100% 或服务上报 Full 单独作为依据。
