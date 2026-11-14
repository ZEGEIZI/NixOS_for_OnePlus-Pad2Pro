# 迁移进度（2026-11-13～14）

**迁移已于 2026-11-14 完成。** 当前日常内核为官方 Linux **7.3.4-erhai-p5**，独立补丁集 23 项；交叉与平板完整原生系统均已构建并验证。原生冷启动、默认 current 普通重启、显示／触控／GPU／扬声器／Wi-Fi／蓝牙／充电／休眠恢复通过，8 核在线、taint=0。声明式配置已安装到 /etc/nixos，标准重建及再次激活后账户完整保留，重启后可登录。菜单仅 current 原生 p5 与 previous 原 7.2.15 恢复入口，/boot 默认只读。详见 full-native-system-p5-validation.json、native-p5-device-acceptance.json、daily-p5-installation.json 和 validation-signoff-p5.json。

以下为迁移过程的历史记录，阶段中的 pending／旧版本不代表当前状态。

- 完成：已有 NixOS 工作区备份；确认设备当前运行 7.2.15；初始目标 7.3.3 来自当时 nixpkgs，已向前更新到 7.3.4。
- 完成：279 个变更文件拆为 15 个提取组，Git tree 与原设备提交完全相等。
- 完成：逐组前移到 7.3；排除 4 个仓库协作文件，部分驱动已由上游覆盖。
- 完成：38 个冲突文件的初步语义合并；保留上游面板驱动，新增 XN242 独立匹配。
- 完成：正式 7.3.3 和 7.3.4 tarball 均通过无模糊重放与结果文件哈希核对；p2 为 20 个补丁、254 个变更文件；p3 新增 VDDIO 约束修复。
- 完成：NixOS 声明式打补丁、最终配置生成与全部配置片段核对；保留 BTF/sched_ext、内建设备驱动。
- 完成：Wi-Fi 固件路由、CPS8601 八项故障注入、85 项启动发布等回归检查；Nix 内严格重放通过。
- 完成：18 补丁版本的完整内核、模块和 DTB 构建；核对 ARM64 Image、模块 release 与 vmlinux BTF。
- 完成：63 个关键驱动对象、9 个 Wi-Fi 对象、实际 DTB 频率策略及全部 25 个变更绑定的 dt-schema 文档校验。
- 完成：修复 Gunyah CMA 绑定后导出 19 个补丁，严格重放及最终完整内核、模块、DTB 构建通过；见 full-kernel-build.json。
- 完成：最终源码的设备驱动回归、Wi-Fi／充电固件测试及 85 项启动发布回归。
- 完成：原生 ARM64 配置生成及全部片段要求检查；平板日常入口使用原生内核，电脑候选保留交叉构建。
- 完成：当前 nixpkgs 的 Mutter 51.0 与前移设备补丁后的 Mesa 26.3.0 完整构建。
- 完成：p1 完整系统、initrd 与离线启动树构建和载荷校验；全部 Wi-Fi／蓝牙固件、CPUCP 模块及 USB 管理服务已确认进入 initrd。
- 实机失败：p1 选择后立即重启，无文字、无 SSH 或新 pstore／journal；用户已回到原代际，默认恢复为原 current。
- 完成：p2 完整内核、模块、DTB、系统、initrd 与启动树构建及校验；64 个关键对象、BTF、模块 release 和相关回归通过。
- 实机失败：p2 同样立即重启；限制 PDC 寄存器读取未解决故障，不能视为已定位原因。
- 实机失败：同一 p2 加单核及早期诊断参数仍立即重启；这次恢复后取得新的 249481 字节 ramoops console，存在明显数据损坏，但可辨认出候选身份及启动过程。
- 新证据：日志到达 UFS 分区探测、SoCCP 启动和 DRM 初始化，末尾为约 0.867 秒的 GMU 固件版本消息；无可辨认 panic／调用栈。见 early-debug-device-boot.json，不能仅凭末条日志认定 GPU 故障。
- 诊断启动成功：仅增加 msm.skip_gpu=1 的入口（af6d9449）已由 SSH 核对系统路径、参数与 boot ID；Wi-Fi 联网，无 systemd failed unit。用户确认黑屏但不自动重启。
- 诊断限制：该参数也阻塞 GMU 依赖的共享 DRM 组件绑定，因此没有 /dev/dri 和声卡；单核及其他诊断参数仍在，不能用于日常验收。故障范围为 GPU 初始化及其耦合的显示依赖。
- 完成：重新生成并比较旧、新 GPU 寄存器头，既有寄存器地址没有变化；GBIF_CX_CONFIG 只是改名。见 gmu-register-audit.json。
- 新证据：SCM 跟踪入口仍立即重启，但 GPU 寄存器初始化及 Zap PAS 认证返回成功。函数跟踪进一步确认 Zap 函数返回 0、安全模式切换及后续等待均完成，末条为约 0.921080 秒的 a6xx_gmu_clear_oob 入口。见 scm-trace-device-boot.json 与 gpu-trace-device-boot.json，尚不能证明该函数是否返回或把故障归因于该寄存器写入。
- 新证据：trace2 确认 GMU clear、a8xx_hw_init、msm_gpu_hw_init、adreno_load_gpu 均返回，帧缓冲创建也返回 0，之后立即重启。见 gpu-trace2-device-boot.json；首次显示模式设置和异步 GPU 省电仍需区分。
- 新证据：fb.lockless_register_fb=1 暴露了更晚的日志：首次 modeset、两次 PHY 和 DSI 主机上电均完成，GPU runtime suspend 的 gmu_stop 也返回 0，最后进入 novatek_nt36536_prepare。见 display-trace-device-boot.json。面板源码与旧自定义驱动比较，仅 DSC 接口及设备／驱动命名不同，供电／复位／上屏命令未改。
- 新证据：panel-trace（4dc3cfe7）仍立即重启；最后可辨认的事件是面板 vreg_l12b_1p8 上电完成，尚无偏压／复位／DCS 事件。KTZ8868 的 is_enabled 仅读缓存，enable 只切 GPIO，不涉及 I²C；下一步区分 regulator 调用与其前面的 2–3 ms 休眠及 CPU idle。见 panel-trace-device-boot.json。原生完整构建仍待补齐。
- 新证据：power-trace（3849e76d）仍立即重启；GPU runtime suspend 与面板 VDDIO regulator_enable 均返回 0，最后进入 usleep_range_state(2000,3000)，未记录返回或偏压调用。无可辨认 panic，下一步仅加 cpuidle.off=1 做对照，不能视为永久方案。见 power-trace-device-boot.json。
- 新证据：noidle-debug（a9496e2c）仍立即重启；日志确认 cpuidle.off 已生效，面板首次休眠未返回，GPU runtime suspend 在其间返回 0。单独关闭 cpuidle 未绕过故障，继续跟踪 generic runtime PM／电源域／SMMU／时钟；见 noidle-debug-device-boot.json。
- 新证据：rpm-trace（5ef2ee0d）仍重启；面板首次休眠期间，GPU 多个时钟关闭／unprepare 完成，最后可辨认事件是 gpu_cc_cxo_clk 的 unprepare_complete，仍无调用栈。该事件位于父时钟递归及 runtime PM put 之前，不能证明函数返回。见 rpm-trace-device-boot.json。下一步延后 DRM 内核客户端和 GDM 上屏，尝试通过 SSH 分开测试 GPU 打开／挂起及 modeset。
- 诊断启动成功：manual-drm（2c1dafde）经 SSH 确认候选身份、空 DRM 客户端／fbdev 关闭，DRM 节点与声卡均出现，无失败服务。单独打开 GPU 并保持 runtime PM on 成功，资源枚举正常；但显式指定主平面的 atomic modeset 仍在面板 VDDIO 供电开始后重启。GPU 自动挂起不是重现故障的必要条件。用户已再次进入同一诊断入口，准备补充 RPMh 请求跟踪；见 manual-drm-device-boot.json。
- 完成：按用户要求清理失效／被替代启动项，回收约 148 MiB；菜单仅保留原 current、previous 和最新诊断项。发布及清理结束后 /boot 均为只读，元数据及恢复入口校验通过；见 debug-boot-cleanup.json。
- 已恢复分区：强制重启后 /boot 的 ext4 needs_recovery 标志导致 kShimC 拒绝读取。已经 Android ADB root 核对分区 UUID／大小并完整备份，在副本演练后仅回放实机日志；只读 fsck 及完整读回的运行时解析器检查通过，7 个入口和全部载荷哈希均正确。见 boot-filesystem-recovery.json，用户已确认实机启动项恢复并进入原 current。
- 预防：后续诊断配置只读挂载 /boot 并关闭自动入口清理，避免强制重启再次隐藏恢复入口。
- 完成：7.3.3 → 7.3.4 前向移植并删除已上游化修改，详见 forward-7.3.4.json。
- 待完成：新候选实机功能验收及默认切换。p1 已验证保留的原代际仍可启动；本轮未提升日常默认内核。

原工作区备份：`../kernel-git-backups/20261113-patchset-migration/`。
原开发分支、旧可启动代际及历史验证记录保留，不新增旧版适配。

原生构建补充：p2 原生配置已重新生成并通过全部片段核对；与交叉配置的有效值仅编译器名称不同（同为 GCC 16.2.0）。第二次完整原生构建在内核解包阶段被手动启动测试中断，未产生完整内核，见 native-config-p2-validation.json 与 native-build-p2.json。

p3 发布：完整参数 179 字节，最终 DTB 的 VDDIO min/max 均为 1896000；原 current／previous 和系统 profile 保留。当前正在运行 manual-drm，暂保留 4 项，进入 p3 后再删除该诊断项，不能提前删运行入口。ARM64 原生配置和补丁源码准备已完成；原生完整内核待正常 p3 验收后运行。蓝牙在受控单核系统中的 UART 外设握手超时尚待正常 p3 复查。

p3 正常启动后已清理旧 manual-drm 入口；当前菜单为原 current、previous 和 p3，启动分区只读。p3 蓝牙仍在首次 UART 握手处超时，不能以服务尚在重试时的零失败数判为通过。

p4 完整交叉内核、模块、DTB、系统、initrd、启动树和源重放／驱动／Wi-Fi／CPS8601／85 项发布回归通过；实际 DTB 仍为 1.896V，启动参数无诊断项，蓝牙实机确认待完成。详见 full-system-p4-validation.json。

p4 运行记录见 normal-p4-device-boot.json：蓝牙两次固件启动均返回0，用户确认开关和连接使用；休眠成功计数2、失败0，RTC 自动休眠约20秒。菜单清理为原 current、previous 和运行的 p4，启动分区只读。原生完整系统构建正在进行，尚未提升 profile。

p5 交叉完整内核构建通过，实际模块 vermagic 为7.3.4-erhai-p5，AArch64／BTF 正确，VDDIO为1.896V，实际 DTB 的 ADSP 堆为 no-map 且无 reusable。内核 postInstall 必检和设备回归均通过。完整系统／原生构建／实机验证仍待完成，见 full-kernel-p5-validation.json。

p5 完整交叉系统、initrd 和启动树已在电脑通过无特权 ARM 用户态仿真构建，输出与预先求值一致。最终启动 DTB 的 ADSP 堆、VDDIO、BTF、模块目录、所有固件和载荷哈希校验通过，入口 ID 为ee22dcee（尚未发布到设备）。完整原生内核及 p5 实机验收仍待完成，见 full-system-p5-validation.json。

p5 ARM 配置与补丁源码准备已在电脑的用户态仿真环境完成，全部最终配置片段检查通过；与交叉配置的有效值仅 GCC 名称不同，同为当前 nixpkgs 的 GCC 16.2.0。见 native-config-p5-validation.json。这不计作平板上的完整原生构建；p5 实机验证和日常提升仍待完成。

p5 已在用户手动恢复原 current 后发布，入口 ee22dcee；实际载荷哈希及菜单校验通过，旧 p4 已清理，菜单仍保留原 current、previous 和 p5。发布后 /boot 为只读，原 profile 和 /etc/nixos 保留；等待手动启动 p5，详见 p5-candidate-publication.json。

p5 已由用户确认进入桌面；SSH 核对 8 CPU 在线、taint=0。实际 ADSP 堆 0xfec00000..0xff7fffff 在 memblock 为 NOMAP，与 System RAM 无重叠；8 进程并发 2 GiB THP 的四轮分配／采样／释放通过，累计写入 8 GiB，taint 仍为0。详见 normal-p5-device-boot.json。下一步完整物理 ARM64 原生构建及启动验收，尚未提升日常默认。

p5 完整物理 ARM64 原生内核、模块、DTB、系统、initrd、启动树和 dev 输出已在平板成功构建，构建结束 taint=0。原生配置、模块 vermagic、BTF、全部固件和载荷、ADSP 保留区及实际 fstab 的 ro,noatime 检查通过。原生入口 9bfa09dd 已保护式发布，旧 current/profile 保留；等待用户冷启动原生版本。详见 full-native-system-p5-validation.json。此前一次构建仅因用户普通重启中断，已单独保留记录，不计作编译失败或内核故障。
