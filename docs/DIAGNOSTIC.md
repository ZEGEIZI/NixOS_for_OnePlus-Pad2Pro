# RAM 诊断启动

这个测试运行 NixOS 生成的 systemd initrd，不切换到已安装根系统，不挂载平板的
任何文件系统，不改变密码、分区或 Android 启动镜像。它不能替代正式安装验收。

```sh
nix build .#nixosConfigurations.pad2pro-probe.config.system.build.diagnosticPayload -L
python3 tools/pack-probe.py \
  --payload result \
  --kshim-project /path/to/kShimC-oneplus-pad2-pro \
  --boot-tools /path/to/verified-ext4-boot-tools \
  --stock-boot /path/to/original-boot.img \
  --output ./probe-v1
```

`--boot-tools` 必须由独立 kShimC 的固定源码构建，且 `result.json` 验证通过。
`--stock-boot` 必须是该设备匹配来源的原始 Android v4 boot，不是已注入 kShimC
的运行中镜像；上游打包器会拒绝再次打包已修改镜像。
`pack-probe.py` 将诊断命令行写入临时 DTB 的 `/chosen/bootargs`，然后调用独立
项目的打包器。输出的 `probe.json` 和 `packed/result.json` 记录摘要和未实机验证状态。

测试由用户手动执行，对照发布时提供的完整路径、版本和 SHA-256：

```sh
fastboot boot /absolute/path/to/probe-v1/packed/boot.img
```

这份临时 debug 镜像的内置基础 Image 是诊断 Linux；正常持久 Android 启动镜像
不受它更改。不要将其 `fastboot flash` 到 Android 分区。

USB NCM 出现后，在电脑给对应接口配置 `192.168.77.10/24`，读取：

```sh
curl --fail http://192.168.77.2:8080/
curl --fail http://192.168.77.2:8080/dmesg.txt
curl --fail http://192.168.77.2:8080/cgi-bin/status
curl --fail http://192.168.77.2:8080/cgi-bin/dmesg
```

报告标志为 `NIXOS_PAD2PRO_INITRD_READY_v1`，随后显示内核 release、内存、设备树
兼容标识及块设备信息。v2 增加两个固定的只读 CGI：按请求读取挂载、CPU 调频、
温度、电池、显示及最新内核日志；不接受或执行客户端提供的命令和参数。
内核日志可能含本机标识，分享前请检查并去除地址/校准等信息。

本测试不含自动超时重启；可通过硬件按键强制重启返回原有持久启动链。
若 USB 未出现，记录屏幕上的最后输出和是否进入文本控制台，勿据此重复刷写。
