# 随仓库提供的固件

基础、Wi-Fi 和蓝牙三个通用固件归档随本项目保存在
`inputs/firmware/archives/`，使用普通 Git 文件。正常克隆会取得全部输入，
不需要 Git LFS、手动下载、从其他项目复制固件或执行 `nix-store --add-fixed`。
`inputs/local/` 不再参与构建。

| 归档 | 文件清单 |
| --- | --- |
| `opd2413-base-firmware.tar` | `inputs/firmware/base.json` |
| `opd2413-wifi-firmware.tar` | `inputs/firmware/wifi.json` |
| `opd2413-bluetooth-firmware.tar` | `inputs/firmware/bluetooth.json` |

`inputs/firmware/archives.json` 固定归档的大小、SHA-256 与对应清单。
Nix 在求值时核对归档摘要，安装时再次核对全部成员、类型、大小和内容摘要。
基础清单排除被替换的通用 WCN7860 Wi-Fi 文件；六个 OEM Wi-Fi 文件整套安装，
蓝牙单独打包。拓扑由 `packages/audio/` 的源码构建；固件和拓扑同步进入 initrd。

```sh
nix build .#checks.x86_64-linux.firmware-inputs
nix build .#firmware .#bluetooth-firmware
```

归档只包含清单中的通用固件和发行版默认 NVM。文件与当前通过实机验收的 p5
保持一致，不包含工厂分区、实际蓝牙地址、序列号、配对密钥或个人校准数据。
每台设备的蓝牙身份由本项目服务在运行时只读解析它自己的工厂分区，不进入构建输入。

原始厂商许可和来源信息保存在清单、`ORIGINAL-NOTICES.md` 与根目录 `NOTICE`；
这些二进制保持原许可，不采用项目或内核的源码许可。

## 维护者更新固件

普通构建无需下列操作。维护者采用新固件时，先更新逐文件清单，按其中的安装路径
整理原始文件，再用确定性打包工具生成新归档：

```sh
python3 tools/firmware_archive.py FIRMWARE_ROOT NEW_BASE.tar
python3 tools/wifi_firmware.py FIRMWARE_ROOT NEW_WIFI.tar
python3 tools/bluetooth_firmware.py pack FIRMWARE_ROOT NEW_BLUETOOTH.tar
```

将验证后的归档替换进 `inputs/firmware/archives/`，同步 `archives.json` 中的大小和
摘要，审查完整成员与设备身份排除规则，再构建和实机验收。打包器不覆盖已有目标。
归档、清单与摘要作为同一次变更发布，不能只更新其中一个。
