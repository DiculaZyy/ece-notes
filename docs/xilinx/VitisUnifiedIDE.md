# Vitis Unified IDE

Xilinx 在 2023.2 版本对 Vitis 进行了重大升级。
新版的 Vitis Unified IDE 与之前的 Vitis Classic IDE 及 SDK 差异显著。
尽管相关文档不少，但新版资料常与过时内容混杂，不易查找。

本文整理了新版 Vitis (2024.2) 的相关资料，并介绍其基础使用流程。

## 开发流程

可以参考以下官方教程：

- [Using the Zynq SoC Processing System](https://github.com/Xilinx/Embedded-Design-Tutorials/blob/master/docs/Getting_Started/Zynq7000-EDT/2-using-zynq.rst)
- [Getting Started in Vitis Unified Embedded IDE](https://github.com/Xilinx/Vitis-Tutorials/tree/2024.2/Embedded_Software/Getting_Started)

### 硬件平台的创建

Vivado端的配置过程仍然和之前基本相同。

新版引入`Extensible Vitis Platform`概念，
支持在导出 .xsa 文件时只包含预合成信息，
后续由 Vitis 调用 Vivado 完成综合和布线。
不过这主要面向硬件加速场景，对纯嵌入式开发用途有限。
所以对于纯嵌入式开发仍然可以选择导出包含bitstream的xsa文件。

新版Vitis使用系统设备树(SDT)管理各种外设和驱动，
类似于Linux中的设备树的概念，
在创建platform时，
Vitis会自动生成SDT并导入相关的驱动。
参考：

- [UG1647](https://docs.amd.com/r/en-US/ug1647-porting-embeddedsw-components)。
- [System Device Tree Generator](https://github.com/Xilinx/system-device-tree-xlnx/tree/master)

### 软件开发

在左边栏的Examples中有很多样例模板，
可以在此基础上编写程序。

#### 结合Vs Code开发

虽然新版Vitis对UI进行了大改，
但编码体验仍有不足,
比如linter有时会崩溃。
不过好消息是新版Vitis使用clangd作为lint工具，
在软件平台目录下可以看到`compile_commands.json`文件，
所以在Vs Code或者其他编辑器中配置好clangd工具后，
可以直接进行代码的编写。

官方Wiki中提供了旧版Vitis和Vs Code结合使用的教程：
[Vitis Debug & Development with VS Code](https://xilinx-wiki.atlassian.net/wiki/x/IgCMgQ)

### 硬件平台的更新

如果修改了设计，
需要重新生成xsa文件，
并在platform设置中浏览并选择新的xsa文件，
不过如果改动太大的话还是建议重新创建platform。

???+ warning

    调试中加载的bitstream在Application的调试配置目录`_ide/bitstream`下，
    在更改xsa文件后，
    这个bitstream不会自动更新！

    这里提供一个简单的应用新bitstream的方法：
    在调试配置界面中手动删除原调试配置，
    再重新生成调试配置。

## 裸机外设驱动的使用

官方驱动Wiki：
[Baremetal Drivers and Libraries](https://xilinx-wiki.atlassian.net/wiki/x/kYAfAQ)

源代码：
[embeddedsw](https://github.com/Xilinx/embeddedsw/tree/master)

可以看到新版的驱动代码加入了`SDT`宏定义，
这主要是为了兼容老的代码，
开发新内容时建议加上这个宏定义。

新版驱动的初始化参数由ID变为了基地址，
相应的`xparameters.h`文件的变化也很大，
特别是中断的配置，
在移植旧版代码时一定要注意。

### 中断的配置

新版Vitis使用`interrupt_wrap`库替代了原版的中断配置，
中断的配置变得更简单了。
可以参考[Interrupts made easy in the Vitis Unified IDE](https://adaptivesupport.amd.com/s/article/Interrupts-made-easy-in-Vitis-Unified-IDE?language=en_US)。
驱动的样例代码中也基本都加入了新的配置方法。

???+ warning

    由于采用了完全不同的配置方式，
    新版Vitis生成的
    `xparameters.h`
    文件中已经不再带有原先的以
    `XPAR_FABRIC_`
    开头的中断号，
    不建议再使用旧的中断配置方式，
    很可能产生问题。

### 自定义外设驱动

使用AXI接口和PS相连的模块可以看作是用户创建的外设，
为了开发相应的驱动，
需要编写对应的YAML/CMAKE文件。

[Creating an SDT enabled baremetal driver template for Vitis Unified IDE](https://adaptivesupport.amd.com/s/article/Creating-an-SDT-enabled-baremetal-driver-template-for-Vitis-Unified-IDE?language=en_US)
这篇文章中提供了一个快速生成外设驱动模板的tcl脚本，
可以在此基础上开发自定义驱动。

再Tcl Console中执行

```tcl
source create_driver.tcl
```

通过help可以查看使用方法

```tcl
help -create_driver
```

???+ tips

    注意到生成的驱动名称是和ip核名字相关的，
    脚本仅仅是将首字母大写并加入了X的前缀，
    如果外设是Block Design并使用自动生成的wrapper的话，
    名字中就会带有`_wrapper`的后缀，
    比较丑。
    不过可以将Block Design导出为ip核重新命名，
    或者也可以试着修改脚本。

可以看到生成的驱动有`data`，`examples`，`src`三个文件夹，
和官方的驱动类似，
`src`文件夹下有CMake的配置文件还有源代码，
其中`_g.c`文件会在创建设备树时自动设置，
不需要管。
`data`文件夹下包含有`yaml`配置文件，
Vitis通过这个文件识别外设对应的驱动。
配置文件都已经自动生成完毕了，
一般来说只需要修改源代码就可以。

驱动编写完成后，
可以在菜单栏的`Vitis/Embedded SW Repositories`中添加驱动的目录。
脚本生成的目录是`repo/XilinxProcessorIPLib/drivers/...`的结构，
添加`repo`的路径即可。

???+ warning

    Vitis似乎只会在创建platform时才会查找驱动，
    建议提前准备好驱动文件，
    以免需要重新创建platform。

    此外Vitis会将所有驱动的源代码复制到工程文件夹下，
    在库中进行的修改并不会自动同步，
    但是可以通过重新生成BSP导入。

    如果修改了驱动，一定要注意。

## 参考资料

[Xilinx Wiki](https://xilinx-wiki.atlassian.net/wiki/spaces/A/overview#Welcome-to-the-Xilinx-Wiki!)

[Vitis-Tutorials](https://github.com/Xilinx/Vitis-Tutorials)

[Embedded-Design-Tutorials](https://github.com/Xilinx/Embedded-Design-Tutorials/tree/master)

[Vitis_Embedded_Platform_Source](https://github.com/Xilinx/Vitis_Embedded_Platform_Source)
