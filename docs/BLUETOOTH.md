# 蓝牙：首次安装自动读取原厂地址

当前固件/驱动已切换为本机 OEM Brahma 方案，见 [原厂蓝牙方案](BLUETOOTH-OEM.md)。
本文的原厂身份读取机制继续使用；开机连接策略见 [蓝牙自动连接](BLUETOOTH-AUTOCONNECT.md)。
下面保留早期 Ganges 固件组合的验收记录。

已验收版本的源码摘要、部署闭包与验证范围保存在
[蓝牙验证清单](BLUETOOTH-VALIDATION.json)。该清单不包含单机地址、序列号、
原始工厂记录或配对密钥。跨发行版源码包为
`artifacts/opd2413-bluetooth-1/opd2413-bluetooth-1.tar.gz`，同目录保存 SHA-256
校验文件；包内包含初始化程序、通用服务、NixOS 包装、测试和来源说明。

2026-11-12 已查明 OPD2413 的原厂蓝牙地址来源，并实现无需 Android 导出地址、
无需人工预置文件的初始化。保留当前 color1 内核、驱动和固件，使用标准
`socinfo` 接口及 Linux Bluetooth MGMT 接口。

## 原厂数据来源与证据

在本机 Android 16（增量版本 `V.54cdc84-304c441-307540c`）开启蓝牙后，
核对了蓝牙 HAL、`/odm/bin/nvram_qmi` 和 `/odm/bin/nvram_server` 的实际调用：

1. `nvram_server` 访问 GPT 标签为 `nonmodemst1`、`nonmodemst2` 的冗余工厂分区。
2. `nvram_qmi` 将 OEM record 0 中的蓝牙字段通过 QMI DMS Get MAC Address
   （service 2、message 0x005c、Bluetooth 类型）提供给 HAL。
3. HAL 将地址交给 WCN7860；Android 的适配器配置与之前保存的本机地址一致。
   `persist.vendor.service.bdroid.bdaddr` 中的表示与适配器显示的字节顺序相反，
   不能直接把属性文本当作正常顺序的地址。

两个工厂分区的首条记录均成功解码，头部与载荷 SHA-256 校验通过，地址与
Android 适配器完全一致。Android 和 Linux 的 `socinfo` 序列号也一致。
Android 原设备树中没有该地址；本机的实际地址传递由厂商用户空间服务完成。

Linux 实现直接只读提取工厂数据，不依赖运行 Android 的 QMI 服务，不启动
厂商 daemon，不修改原分区，不生成替代地址。厂商二进制和设备数据不进入 Git
或 Nix store。程序仅实现已验证的记录格式；不同格式或校验失败会明确报错。

## 初始化与持久保存

`modules/bluetooth.nix` 随硬件模块导入。启用蓝牙时：

- 通过 `boot.kernelModules` 显式加载现有的 `socinfo` 模块。
- 在 `local-fs.target` 和 `systemd-modules-load.service` 后、BlueZ 前执行
  `pad2pro-bluetooth-address.service`。
- 从 `/sys/devices/soc0/serial_number` 获取本机 SoC 标识；只读访问每份工厂
  分区首个 4096 字节，解码并校验头部和载荷。
- 两份有效数据的地址必须一致；一份损坏时使用另一份有效副本并记录原因，
  两份都无效或有效副本冲突时停止，不猜测地址。
- 首次启动原子创建 `/var/lib/oneplus-pad2pro/bt-address`，root 所有、0600；
  后续启动重新与工厂数据核对，拒绝把另一台机器的缓存身份应用到本机。
- 通过原生 MGMT socket 设置地址，并等待实际读回成功；已有相同地址时幂等成功，
  已有不同地址时拒绝覆盖。只处理 OPD2413 的 898000 UART，忽略 USB 适配器。

服务不主动打开蓝牙电源，由 BlueZ/GNOME 恢复用户选择的状态。程序不解析
`btmgmt` 的文本输出，也不依赖它的交互终端行为。

缓存文件可以随普通系统更新保留；重装后即使没有缓存，也能从本机工厂分区
重新提取。通用镜像必须排除缓存文件，保留原厂 `nonmodemst1/2` 分区。
工厂分区被擦除或不再可读时，不能承诺自动恢复原厂身份。

## 工厂记录格式

格式由上述 Android 实现和实机数据交叉核对，代码位于
`tools/bluetooth_factory.py`。这里只实现 OEM record 0：

- 单元大小 4096，未加密头部 448 字节，魔数 `OEM~~OEM`。
- 小端头部字段包含 record ID、载荷长度、加密额外长度和状态；读取完整状态 2。
- SoC 序列号按 `%015X` 加 NUL 编码为 16 字节，SHA-256 后进行三次偶数/奇数
  字节重排及位旋转，结果前 16 字节为 AES-128-CBC key，后 16 字节为 IV。
- 解码结果包含头部 SHA-256、载荷 SHA-256、载荷和对齐字节。
- OEM 载荷偏移 998 的 6 字节为蓝牙地址，使用 HCI 小端顺序。

程序检查所有长度边界、双重摘要、地址非空及副本一致性。偏移只用于已识别并
通过校验的 OPD2413 记录；不会在分区中搜索看起来像 MAC 的任意字节。

## 启动异常与恢复

本次从 Android 返回 NixOS 时，固件出现 `0xfc00` 超时和内核重试，约 95 秒后
完成 setup，超过旧版服务的 90 秒等待期限，旧服务因此失败。

新服务每次等待最多 90 秒，超时返回 EX_TEMPFAIL（75），由 systemd 进行有次数
限制的重试（600 秒内最多 3 次启动，间隔 2 秒）。工厂数据错误和身份冲突返回 1，
不自动重试。BlueZ 不会因一个初始化任务无限等待。此措施覆盖晚到的控制器，
不代表底层固件超时本身已修复；持续出现时应在共享内核仓库调查。

## 跨发行版复用

`tools/bluetooth-address.py`、`tools/bluetooth_factory.py` 和
`tools/bluetooth_mgmt.py` 是发行版无关的 Python 程序，依赖 Python 3 和
`cryptography`，通过稳定的 Linux MGMT 协议与内核交互。通用 systemd 服务及
modules-load 配置位于 `support/`，安装方法见 [共享设备支持说明](../support/README.md)。
NixOS 的包装在 `packages/bluetooth.nix` 和 `modules/bluetooth.nix`。
驱动、设备树和硬件配置仍由共享内核维护，服务及发行版打包留在用户空间项目。

## 验证范围

- 本机 Android 与 Linux 原厂数据读回一致，两份工厂记录和双重摘要通过。
- 在 NixOS 上使用一个不存在的状态文件路径，自动创建地址并配置未初始化的 hci0，
  与旧的 Android 地址文件完全一致，权限 0600；未预先向该路径复制任何地址。
- 29 项蓝牙回归和全部 52 项主机回归通过，覆盖坏副本、错误硬件标识、越界、
  头部/内容损坏、身份冲突、原子保存、MGMT 编解码和实际地址读回。
- 新系统构建、`nixos-rebuild test` 和新服务执行通过，系统失败服务为 0。
- 内核、模块、设备树和桌面软件路径与已验收基线一致，未改固件二进制输入。

已通过 `nixos-rebuild switch` 持久发布为 `nixos-06f3e4b35a208da7db344a74adbfc516`，
系统 profile 为 `/nix/store/g4k4c9zyappd43ic9ndj4d0alhy14w1m-nixos-system-pad2pro-26.11.20261107.f4a03c0`，
前一代为 `nixos-2af73f38e20880389bdde24bbabf14bd`。按用户明确要求，删除最旧的
`NixOS GNOME HDR v1`（`nixos-5e7103ffe05939a2a6e8b6e2bfb467ff`）启动目录及其
GC root，不做载荷备份，给旧版菜单腾出位置；未运行 store GC。保留的 8 个入口
均通过载荷校验，默认仍为 `nixos/current`，启动分区恢复只读。

77 个实际固件文件的摘要与变更前一致；固件包路径和 initrd 因依赖路径变化
重新生成，内核二进制、模块和设备树未替换。
已在重启前删除默认地址缓存，随后通过真实正常重启验收：实际启动上述新代际，
开机服务约 1.9 秒成功完成，无重试，自动从两份工厂数据恢复地址并创建 root/0600
缓存，MGMT 地址读回成功。系统失败服务为 0，蓝牙自动开启，实际扫描到 7 个
附近设备。新启动的 GNOME 界面尚未单独取得用户确认；实际配对/重连、音频播放、
其他 ROM 和第二台实机仍待验收。
第二台同型号设备依靠自己的 SoC 标识及工厂分区初始化，不需要使用本机数据。

本机私有采集和验证材料保存在电脑 `.work/bluetooth-android-source/`（目录 0700）；
平板的构建链接、原服务失败日志和空状态测试文件保存在
`/var/lib/pad2pro-updates/bluetooth-factory/`。旧版手工预置方案的历史资料仍保留在
`/var/lib/pad2pro-updates/bluetooth-address-before/`。
