本项目独立维护 OnePlus Pad 2 Pro 的 NixOS 配置、打包、服务、initrd 和启动发布。
设备支持依赖 linux-sm8750-erhai-patchset，启动协议及菜单依赖 kShimC-oneplus-pad2-pro。
两个依赖以 inputs/ 下的可校验快照接入；日常构建、安装和更新不读取其他项目工作区。
不得重新引入 armadaos-freedom 或 onepluspad-2pro-mainline 作为构建、运行或维护前提。
移植来源与版权记录属于归属信息，保留 NOTICE、源码许可及历史证据。
目录职责与依赖更新方法见 docs/DEVELOPMENT.md；固件准备见 docs/FIRMWARE.md。
普通用户克隆后即可取得所有设备构建输入；通用固件归档随 Git 保存于 inputs/firmware/archives/，构建自动校验，不要求手动导入 Nix store 或复制 inputs/local。设备身份与配对数据不得进入通用归档。
在调试阶段，你可以修改kShimC的默认启动项，选择你要进入的系统，增加调试自动化的程度

驱动、设备树和硬件基础配置在独立补丁集项目维护；本项目只同步发布快照，不直接编辑 inputs/kernel-patchset。
音频拓扑、UCM、Mesa 与桌面集成由本项目维护，不通过其他发行版项目获取。
显式新内核构建使用本项目的 packages/nixos.config，不要求内核源码提供 NixOS 专用文件。
所有内核构建和模块聚合统一使用当前 nixpkgs 的工具链，不保留独立旧工具链，不以历史闭包路径断言阻止工具链更新。实机验证记录作为历史信息，不作为固定构建产物的门禁。
普通用户自行选择用户名。本项目不预置普通账户，也不在公共或本机配置中按个人用户名、UID 或家目录绑定偏好。Shell、桌面、输入法、音频等共享设置使用系统级默认值或通用用户服务；账户由 GNOME 用户管理或标准账户工具管理。
移除已有受管账户的声明前必须备份账户数据库并安排安全迁移；users.mutableUsers = true 不保证撤掉旧声明后仍保留该账户。迁移必须核对原 UID、密码、家目录和附属 UID/GID 范围，并验证再次激活不会删除自行管理的账户。
