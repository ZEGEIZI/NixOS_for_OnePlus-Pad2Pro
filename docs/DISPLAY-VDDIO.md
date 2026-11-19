# XN242 VDDIO：7.3 与 v7.4-dev 对照

2026-11-18 更新。建议保留当前 `7.3.4-erhai-p9` 的 **1.896 V 固定约束**。
板级设备树将面板和触控的共用电源轨限制在已验证的档位。
`onepluspad-2pro-mainline` 默认锁定的 7.4.0-rc2 仍允许 1.904 V。
这里的电压均为软件请求或报告，物理电压尚未独立测量。

## 比较对象

7.4 的主比较对象以参考项目 `kernel/source.json` 的 `kernel.commit` 为准。
参考项目的默认构建脚本验证该提交并编译 `qcom/sm8750-erhai.dtb`。
表中也保留 2026-11-16 对照过的两个本地引用，用于说明旧版驱动的行为差异。

| 对象 | 提交／版本 | VDDIO 行为 |
| --- | --- | --- |
| 本项目的独立补丁集 p9 | manifest head `5b49cde232f03d6df8b3ba40eda505c175de2801`，官方 7.3.4 加设备补丁 | p5 引入的补丁 `0021` 将上下界均固定为 1,896,000 µV |
| `onepluspad-2pro-mainline` 默认构建 | [内核源码提交 `da4b783e34bd`](https://github.com/yzddmr6/linux-sm8750-erhai/tree/da4b783e34bd05d7451a6f904fbf567af1215f99)，Makefile 为 **7.4.0-rc2** | 允许 1,896,000–1,904,000 µV，具备启动电压读回 |
| 历史 `refs/heads/origin/sm8750/v7.4-dev` | `fb18d39b1baeeac3698a8786c134a326235ead9f`，Makefile 实际为 **7.2.15** | 允许 1,896,000–1,904,000 µV，启动电压未知时由 core 初始化 |
| 历史 `refs/remotes/origin/sm8750/v7.4-dev` | `7caab63bcc2ae24bf1df90e1be012c4a5dc3c4ff`，**7.4.0-rc2** | 同一宽范围，具备启动电压读回 |

NixOS 的构建关系为官方 `linux_7_3` → 独立补丁集快照 → 最终内核、DTB 和
initrd；参考 fork 只用于本次比较，不是构建输入。驱动和 DTS 修复继续在独立
补丁项目的源码维护分支完成，再导出和同步，不直接修改 `inputs/kernel-patchset`。

## 为什么相同的宽范围在新内核上表现不同

供电链为 XN242 面板的 `vddio-supply` → `vreg_l12b_1p8` → RPMh `ldob12`。
当前 DTS 使用 `qcom,pm8550-rpmh-regulators`；驱动将其 LDO12 对应到
`pmic5_nldo515`。该模型为：

```text
电压 = 320000 + selector × 8000 µV
selector 197 = 1896000 µV
selector 198 = 1904000 µV
```

这个软件模型没有精确的 1,900,000 µV 档位。关键变化是上游提交
`09d99ff7fc3c802c9b31ded9ffdf992d966a0835`
（`regulator: qcom-rpmh: readback voltage/bypass/mode set during bootup`），
已经出现在本次核对的官方 7.3.4 源码和 7.4-dev 中。

1. 较旧的 7.2.15 驱动以 `-ENOTRECOVERABLE` 表示未知电压；regulator core
   的 `machine_constraints_voltage()` 因而初始化电压，在该区间选中下方的
   1.896 V 档位。
2. 新驱动的 `rpmh_regulator_vrm_get_voltage_sel()` 调用 `rpmh_read()`，
   将读回的 1900 mV 传入 `regulator_map_voltage_linear_range(rdev, uV, INT_MAX)`。
   该映射向上选择 selector 198，缓存值成为 1.904 V。
3. 1.904 V 满足原来的 1.896–1.904 V 约束，core 不会纠正它。
4. `rpmh_regulator_set_enable_state()` 在首次 enable/disable 时，会先发送已缓存的
   电压选择，再发送开关请求。这里并非只有显示数值发生变化：这条路径可以产生
   实际的 **1904 mV RPMh 请求**。
5. p5 将上下界均固定到 1.896 V，使 core 在注册阶段将超出约束的缓存选择改为
   selector 197；首次使能使用 **1896 mV 请求**。

因此，仅看到参考仓库旧代码允许 1.896–1.904 V，不能认为两个档位都经过实机验证；
旧驱动的初始化路径本来就倾向于选中下方档位。

## 7.4.0-rc2 的面板实现

7.4-dev 将 XN242 整合为通用 `panel-novatek-nt36536.c` 中的独立 profile，
使用 `csot_xn242_panel_funcs`。XN242 实际调用专用的
`csot_xn242_power_on()`，没有使用另一面板 profile 的通用 bulk-enable 上电路径：

```text
VDDIO enable → 2–3 ms → VSP enable → 8–9 ms → VSN enable → 10–11 ms
```

这与当前 7.3 XN242 路径的供电顺序一致。虽然供电句柄改为 bulk 数据结构，
XN242 仍逐个使能；该驱动没有为 VDDIO 调用 `regulator_set_voltage()`，
也没有提供精确 1.900 V 的新 PMIC 模型。DSC／面板 profile 的调整不能代替这里的
板级电压约束修复。

逐函数对照确认，7.3.4 补丁集与参考项目锁定的 7.4.0-rc2 具有相同的读回、映射、
缓存、写电压、首次使能和电压约束初始化逻辑。因此，如果该 7.4 构建同样读回 1900 mV，
**宽范围约束会保留 selector 198**。这是源码推导，7.4 的实际启动表现仍待实机验证。

## 证据与判断边界

2026-11-18 通过只读 SSH 检查运行中的 `7.3.4-erhai-p9`。运行时设备树中，
XN242 的 `vddio-supply` 指向 `vreg_l12b_1p8`，上下界均为 `1896000` µV。
启动日志与 sysfs 输出如下。

```text
microvolts=1896000
min_microvolts=1896000
max_microvolts=1896000
state=enabled
num_users=1
card0-DSI-1: connected, enabled, DPMS On
vreg_l12b_1p8: Bringing 1904000uV into 1896000-1896000uV
```

日志确认本次启动触发了约束纠正。sysfs 与 DRM 状态确认采集时驱动已使用该电源轨，
电压读数来自驱动缓存。

既有控制实验见
[`panel-vddio-diagnosis.json`](../inputs/kernel-patchset/provenance/panel-vddio-diagnosis.json)：
同一诊断内核中，GPU 保持供电也会在首次 modeset 时重启；临时加入 1.896 V
消费端约束后成功上屏，跟踪确认发送 1896 mV 电压请求及随后的使能请求，
用户确认可见测试图。随后普通 p5 的验收范围见
[`KERNEL-PATCHSET.md`](KERNEL-PATCHSET.md)。

原厂 Android 的消费端请求、初始化和亮屏驱动报告均为 **1.900 V**，详见
[`android-factory-vddio-reference.md`](../inputs/kernel-patchset/provenance/android-factory-vddio-reference.md)。
1.896 V 比该名义请求低 4 mV，约 0.21%；它是已验证的主线移植设置。
目前证据尚未把物理电压、启动状态接管、读回取整及重新发送电压请求的作用完全分开，
因此不应把现象写成“面板物理耐压上限是 1.900 V”或“已证明高 8 mV 必然导致黑屏”。

2026-11-16 的核查确认官方 7.3.4 tarball 的 SHA-256 与 manifest 一致，其中的
`drivers/regulator/{core,of_regulator,qcom-rpmh-regulator}.c` 与本地 7.3 源码一致；
板级 DTS 与发布 manifest 的结果摘要一致。复查原始输出保存在本机忽略目录
`.work/vddio-comparison-20261116/audit.json`。

## 后续维护选择

- 日常系统继续固定 1.896 V；前移到 7.4 时保留该约束，并核对最终启动 DTB。
  这种板级限制比恢复宽范围更确定，也避免为单一设备改动所有 PMIC 的共用行为。
- 不建议全局禁用 RPMh 读回或把所有电压映射改成向下取整；这会影响其他电源轨，
  且可能低于其他消费端的最低要求。通用驱动改进需单独分析读回的语义和兼容性。
- 若要对齐原厂 1.900 V，先核实实际 PMIC 型号、LDO 子类型和 RPMh 固件如何处理
  毫伏请求，再决定是否修正模型或读回接口。直接在当前 8 mV 模型下把 DTS 上下界
  都写为 1.900 V 没有合法 selector，会使 regulator 注册失败。
- 新电压／驱动候选需独立验收冷启动、Android 往返、重复亮灭屏和休眠恢复，并记录
  实际 RPMh 请求；确认电气根因还需要物理测量。本次没有进行这些新候选实验。
