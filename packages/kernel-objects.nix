{ lib, kernel, selectedObjects ? null }:
let
  objects = if selectedObjects != null then selectedObjects else [
    "arch/arm64/mm/fault.o"
    "drivers/irqchip/qcom-pdc.o"
    "drivers/clk/clk.o"
    "drivers/phy/phy-core.o"
    "drivers/phy/qualcomm/phy-qcom-qmp-combo.o"
    "drivers/phy/qualcomm/phy-qcom-mipi-csi2-core.o"
    "drivers/phy/qualcomm/phy-qcom-mipi-csi2-3ph-dphy.o"
    "drivers/remoteproc/qcom_q6v5.o"
    "drivers/remoteproc/qcom_q6v5_pas.o"
    "drivers/rpmsg/qcom_glink_native.o"
    "drivers/soc/qcom/abl_root_identity.o"
    "drivers/soc/qcom/pmic_glink.o"
    "drivers/soc/qcom/pmic_glink_altmode.o"
    "drivers/pci/controller/dwc/pcie-qcom.o"
    "drivers/pci/pwrctrl/pci-pwrctrl-pwrseq.o"
    "drivers/power/sequencing/pwrseq-qcom-wcn.o"
    "drivers/ufs/host/ufs-qcom.o"
    "drivers/input/keyboard/oneplus-pogo-keyboard.o"
    "drivers/input/touchscreen/nt36536/nt36536.o"
    "drivers/input/touchscreen/nt36536/nt36536_fw_update.o"
    "drivers/video/backlight/ktz8866.o"
    "drivers/thermal/qcom/qcom-spmi-adc-tm5-gen3.o"
    "drivers/spi/spi-geni-qcom.o"
    "drivers/tty/serial/qcom_geni_serial.o"
    "drivers/usb/dwc3/dwc3-qcom.o"
    "drivers/usb/typec/mux/wcd939x-usbss.o"
    "drivers/usb/typec/ucsi/ucsi_glink.o"
    "drivers/usb/gadget/function/f_ncm.o"
    "drivers/power/supply/cps8601.o"
    "drivers/power/supply/sc8547a.o"
    "drivers/power/supply/erhai_pps.o"
    "drivers/power/supply/qcom_battmgr.o"
    "drivers/bluetooth/hci_qca.o"
    "drivers/bluetooth/btqca.o"
    "drivers/bluetooth/hci_serdev.o"
    "drivers/gpu/drm/msm/adreno/a6xx_gpu.o"
    "drivers/gpu/drm/msm/adreno/a6xx_gmu.o"
    "drivers/gpu/drm/msm/adreno/a8xx_gpu.o"
    "drivers/gpu/drm/msm/disp/dpu1/dpu_encoder.o"
    "drivers/gpu/drm/msm/disp/dpu1/dpu_hw_vbif.o"
    "drivers/gpu/drm/msm/dsi/dsi_host.o"
    "drivers/gpu/drm/msm/dp/dp_ctrl.o"
    "drivers/gpu/drm/msm/dp/dp_display.o"
    "drivers/gpu/drm/msm/msm_drv.o"
    "drivers/gpu/drm/panel/panel-novatek-nt36536-erhai.o"
    "sound/soc/codecs/lpass-rx-macro.o"
    "sound/soc/codecs/lpass-tx-macro.o"
    "sound/soc/codecs/lpass-va-macro.o"
    "sound/soc/codecs/lpass-wsa-macro.o"
    "sound/soc/codecs/wcd-common.o"
    "sound/soc/codecs/wcd939x.o"
    "sound/soc/codecs/aw88261.o"
    "sound/soc/qcom/common.o"
    "sound/soc/qcom/sc8280xp.o"
    "sound/soc/qcom/qdsp6/q6apm.o"
    "sound/soc/qcom/qdsp6/q6apm-dai.o"
    "sound/soc/qcom/qdsp6/audioreach.o"
    "sound/soc/qcom/qdsp6/topology.o"
    "sound/soc/qcom/qdsp6/q6prm-clocks.o"
    "drivers/media/platform/qcom/camss/camss.o"
    "drivers/media/platform/qcom/camss/camss-vfe.o"
    "drivers/media/platform/qcom/iris/iris_ctrls.o"
    "drivers/media/platform/qcom/iris/iris_vdec.o"
    "drivers/media/platform/qcom/iris/iris_vpu_common.o"
  ];
in kernel.overrideAttrs (_: {
  pname = "erhai-driver-object-check";
  buildPhase = ''
    runHook preBuild
    failed=0
    for target in ${lib.escapeShellArgs (objects ++ [ "qcom/sm8750-erhai.dtb" ])}; do
      make "''${makeFlags[@]}" -j"$NIX_BUILD_CORES" "$target" || failed=1
    done
    test "$failed" = 0
    runHook postBuild
  '';
  installPhase = ''
    mkdir -p $out $modules
    ${lib.concatMapStringsSep "\n" (obj: "test -s \"$buildRoot/${obj}\"") objects}
    cp "$buildRoot/arch/arm64/boot/dts/qcom/sm8750-erhai.dtb" $out/
    cp "$buildRoot/.config" $out/config
    printf '%s\n' ${lib.escapeShellArgs objects} > $out/objects
  '';
  postInstall = "";
  postFixup = "";
  dontFixup = true;
})
