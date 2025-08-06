# Petalinux 

基于Petalinux 2024.2

## 构建流程

### Vivado设计

导出xsa文件

### 生成SDT

使用Xilinx的[System Device Tree Generator](https://github.com/Xilinx/system-device-tree-xlnx)

参考

- [旧版设备树Wiki](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842279/Build+Device+Tree+Blob)

### 启动Petalinux

```shell
source ${DIR}/settings.sh
```

对于Ubuntu系统还需要加上

```shell
sudo sysctl -w kernel.apparmor_restrict_unprivileged_unconfined=0
sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0
```

来自[Help me get my petalinux working (ubuntu 24.04 --- petalinux-v2023.2)](https://adaptivesupport.amd.com/s/question/0D54U00008PJPRhSAP/help-me-get-my-petalinux-working-ubuntu-2404-petalinuxv20232?language=en_US)

### 从模板新建工程

```shell
petalinux-create project --template <PLATFORM> --name <PROJECT_NAME>
```

参考

- [UG1144 Creating an Empty Project from a Template](https://docs.amd.com/r/en-US/ug1144-petalinux-tools-reference-guide/Creating-an-Empty-Project-from-a-Template)

### 指定硬件设计

```shell
petalinux-config --get-hw-description /<PATH-TO-SDT Directory> 
```

参考

- [UG1144 Setting Up the System Devicetree](https://docs.amd.com/r/en-US/ug1144-petalinux-tools-reference-guide/Setting-Up-the-System-Devicetree)

- [UG1144 Importing Hardware Configuration](https://docs.amd.com/r/en-US/ug1144-petalinux-tools-reference-guide/Importing-Hardware-Configuration)

### System 配置

在指定硬件设计后自动弹出，或输入

```shell
petalinux-config
```

#### 设置离线缓存

1. 下载并解压 [PetaLinux Tools sstate-cache Artifacts](https://www.xilinx.com/support/download/index.html/content/xilinx/en/downloadNav/embedded-design-tools/2024-2.html)

1. 设置Pre-mirror

    填入`downloads/`目录的地址

    ```shell
    petalinux-config ---> Yocto Settings ---> Add pre-mirror url --->
    ```

    需要加入`file://`前缀

1. 设置SState Feeds

    填入sstate镜像目录的地址，如对于Zynq7000来说是`arm/`

    ```shell
    petalinux-config ---> Yocto Settings ---> Local sstate feeds settings ---> local sstate feeds url --->
    ```

1. 关闭网络连接

    ```shell
    petalinux-config ---> Yocto Settings ---> [*] Enable BB NO NETWORK
                                              [ ] Enable Network sstate feeds
    ```

1. 修改配置文件

    在/project-spec/meta-user/conf/petalinuxbsp.conf中加入

    ```bash
    DL_DIR = "/home/share/build/petalinux/2020.2/downloads"
    SSTATE_DIR = "/home/share/build/petalinux/2020.2/sstate_aarch64_2020.2/aarch64"
    ```

参考

- [UG1144 Build Optimizations](https://docs.amd.com/r/en-US/ug1144-petalinux-tools-reference-guide/Build-Optimizations)

- [PetaLinux® ビルド時間の短縮方法](https://www.paltek.co.jp/techblog/techinfo/221209_01)


### Device Tree 配置

在SDT流程中，由硬件设计生成的设备树在`project-spec/hw-description/`目录下，
由用户自定义的设备树配置在`project-spec/meta-user/recipes-bsp/device-tree/files/system-user.dtsi`。

参考

- [UG1144 Device Tree Configuration](https://docs.amd.com/r/en-US/ug1144-petalinux-tools-reference-guide/Device-Tree-Configuration)

### Kernel 配置

需要用到的内核模块

```shell
petalinux-config -c kernel
```

### U-Boot 配置

启动项，引导等

```shell
petalinux-config -c u-boot
```

### RootFS 配置

```shell
petalinux-config -c rootfs
```

??? example

    - `lrzsz`: 使用ZMODEM协议实现串口文件传输

### 构建

```shell
petalinux-build
```

### 打包

需要在`<project-root-dir>/image/linux`下进行

```shell
petalinux-package boot --format BIN --fsbl zynq_fsbl.elf --u-boot u-boot.elf --fpga system.bit --force
```

### 下载到SD卡

```shell
sudo dd if=rootfs.ext4 of=/dev/sda2
cp boot.scr BOOT.BIN image.ub /media/diculazyy/BOOT/
```

### 打包为BSP

```shell
petalinux-package bsp -p <plnx-proj-root> --output MY.BSP
```

参考

- [UG1144 BSP Packaging](https://docs.amd.com/r/en-US/ug1144-petalinux-tools-reference-guide/BSP-Packaging?tocId=Yfr6DSNg_3pRdiRqwGq1yQ)

如果打包报错，可能需要修改脚本

参考

- [ Fix project argument of petalinux-package bsp #4 ](https://github.com/Xilinx/PetaLinux/pull/4/commits/23e00d30c4d0dcf761d05422393717308768ac34)
- [我尝试打包项目BSP文件失败](https://adaptivesupport.amd.com/s/question/0D5KZ00000tSZ6R0AW/%E6%88%91%E5%B0%9D%E8%AF%95%E6%89%93%E5%8C%85%E9%A1%B9%E7%9B%AEbsp%E6%96%87%E4%BB%B6%E5%A4%B1%E8%B4%A5-petalinuxpackage-bsp-p-mediagyxworkfpga1egmydczu1eg-output-mydczu1egv3bsperror-unable-to-create-directory-at-buildgyxbspmediagyxworkfpga1egmydczu1eg-lsbuild-compon?language=en_US)

### 生成SDK

```shell
petalinux-build --sdk
```

```shell
petalinux-package sysroot -s|--sdk <custom sdk path> -d|--dir <custom directory path>
```

参考

- [SDK Generation](https://docs.amd.com/r/en-US/ug1144-petalinux-tools-reference-guide/SDK-Generation-Target-Sysroot-Generation)

## HDMI配置

### Device Tree 配置

```DTS
&i2c0 {
	clock-frequency = <100000>;
	status = "okay";
};

&amba_pl {
	digilent_hdmi {
        compatible = "digilent,hdmi";
        clocks = <&axi_dynclk_0>;
        clock-names = "clk";
        digilent,edid-i2c = <&i2c0>;
        digilent,fmax = <150000>;
        port@0 {
            hdmi_ep: endpoint {
                remote-endpoint = <&pl_disp_ep>;
            };
        };
    };
    xlnx_pl_disp {
        compatible = "xlnx,pl-disp";
        dmas = <&axi_vdma_0 0>;
        dma-names = "dma0";
        xlnx,vformat = "RG24"; /*XR24*/
        xlnx,bridge = <&v_tc_0>;
        xlnx,vtc = <&v_tc_0>;
        port@0 {
            pl_disp_ep: endpoint {
                remote-endpoint = <&hdmi_ep>;
            };
        };
    };
};

&axi_dynclk_0 {
	compatible = "dglnt,axi-dynclk";
	#clock-cells = <0>;
};

&v_tc_0 {
	xlnx,pixels-per-clock = <1>;
};

&axi_vdma_0 {
	dma-ranges = <0x00000000 0x00000000 0x40000000>;
};

&axi_gpio_hdmi {
	compatible = "generic-uio";
};

```

### Kernel配置

配置DRM

```bash
# DRM 核心支持
CONFIG_DRM=y
CONFIG_DRM_KMS_HELPER=y

# Xilinx DRM 驱动
CONFIG_DRM_XLNX=y
CONFIG_DRM_XLNX_BRIDGE=y # KMS支持
CONFIG_DRM_XLNX_BRIDGE_VTC=y # 时序同步

CONFIG_DRM_XLNX_BRIDGE_CSC=m # 可选
CONFIG_DRM_XLNX_BRIDGE_SCALER=m # 可选

# PL端HDMI输出配置
CONFIG_DRM_XLNX_PL_DISPLAY=y # 使用PL输出

```

Frame Buffer 兼容性支持

```bash
CONFIG_FB=y
CONFIG_FB_XILINX=y
CONFIG_DRM_FBDEV_EMULATION=y  # DRM 模拟 fbdev 设备
CONFIG_FRAMEBUFFER_CONSOLE=y # 使用FB显示终端
```

HDMI相关配置

```bash
# EDID
CONFIG_FIRMWARE_EDID=y
CONFIG_DRM_LOAD_EDID_FIRMWARE=y
```

相关外设驱动

```bash
# VDMA
CONFIG_DMADEVICES=y
CONFIG_XILINX_DMA=y

# VTC
CONFIG_VIDEO_XILINX_VTC=y

# IIC
CONFIG_I2C_CADENCE=y

# GPIO
CONFIG_GPIO_SYSFS=y
CONFIG_SYSFS=y
CONFIG_GPIO_XILINX=y

# PIN_CTRL
CONFIG_PINCTRL=y
CONFIG_PINCTRL_ZYNQ=y
CONFIG_ARCH_ZYNQ=y
CONFIG_PINMUX=y
CONFIG_GENERIC_PINCONF=y
```

### U-Boot配置

```bash
# 启动时的视频显示
CONFIG_VIDEO=y

```

### RootFS配置

```bash
# DRM
CONFIG_libdrm=y
CONFIG_libdrm-drivers=y

# 调试
CONFIG_SYSFS=y
```

## USB 触控配置

### Kernel配置

```bash
# HID
CONFIG_HID=y

# 触控
CONFIG_HID_MULTITOUCH=y
CONFIG_INPUT_TOUCHSCREEN=y

# USB输入设备
CONFIG_TOUCHSCREEN_USB_COMPOSITE=y
CONFIG_TOUCHSCREEN_USB_GENERAL_TOUCH=y
```

## LVGL 配置

### Layer 配置

由于LVGL已经包含在openembedded的layer中，
而Petalinux是基于Yocto的，
相关的layer可以在`<plnx-proj-root>/components/yocto/layers`中找到，
所以不需要自行安装。
然而这些recpies默认不会构建，
必须手动执行

```shell
petalinux-build -c lvgl
```

然后在`<plnx-proj-root>/project-spec/meta-user/conf/petalinuxbsp.conf`中添加

```bash
IMAGE_INSTALL:append = " lvgl"
TOOLCHAIN_TARGET_TASK:append = " lvgl"

```

默认的recipe会修改`lv_conf.h`，如果想要修改配置，
必须在构建之前完成，
可以新建`<plnx-proj-root>/project-spec/meta-user/recipes-graphics/lvgl/lvgl_x.x.x.bbappend`，
注意版本号需要匹配，具体可以修改的参数可以参考recipe的`.bb`文件以及`lv_conf.inc`。

参考

- [LVGL in Yocto](https://docs.lvgl.io/master/details/integration/os/yocto/lvgl_recipe.html)
- [How to get meta-oe layer packages installed in PetaLinux image](https://adaptivesupport.amd.com/s/question/0D52E00006iHqktSAC/how-to-get-metaoe-layer-packages-installed-in-petalinux-image?language=en_US)
- [Github - meta-openembedded/meta-oe/recipes-graphics/lvgl](https://github.com/openembedded/meta-openembedded/tree/scarthgap/meta-oe/recipes-graphics/lvgl)

### Kernel配置

### RootFS配置

```bash
# 库
CONFIG_GLIBC=y

# 显示相关
CONFIG_FBSET=y
CONIFG_LIBEVDEV=y
```

### FrameBuffer显示

关闭光标

```shell
echo 0 > /sys/class/graphics/fbcon/cursor_blink
```

## 上板与调试

## 通过JTAG启动

```shell
petalinux-boot jtag --u-boot
```

从TFTP服务器上拉取镜像

```shell
setenv serverip 192.168.1.99
setenv ipaddr 192.168.1.100
tftpboot 0x1000000 image.ub
```

启动镜像

```shell
bootm 0x1000000
```

## 异构设计

由于Zynq中存在多个独立内核，
可以让内核运行不同的系统。
然而Xilinx已经终止了Zynq7000系列的OpenAMP支持。
不过对简单的异构设计来说，
可以通过共享内存和中断实现。

参考

- [UG1144 Building multiconfig Applications](https://docs.amd.com/r/en-US/ug1144-petalinux-tools-reference-guide/Building-multiconfig-Applications)
- [UG585 Zynq 7000 Soc TRM - On Chip Memory OCM](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/On-Chip-Memory-ocm)
- [XAPP1078 Simple AMP Running Linux and Bare-Metal System on Both Zynq Processors Application Note](https://docs.amd.com/v/u/en-US/xapp1078-amp-linux-bare-metal)

### RemoteProc

## 参考资料

[UG1144](https://docs.amd.com/r/en-US/ug1144-petalinux-tools-reference-guide/)

[ZYNQ以后能用到的相关内容](https://sunlee.top/2023/03/21/ZYNQ%E4%BB%A5%E5%90%8E%E8%83%BD%E7%94%A8%E5%88%B0%E7%9A%84%E7%9B%B8%E5%85%B3%E5%86%85%E5%AE%B9/)