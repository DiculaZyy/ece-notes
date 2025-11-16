# LWIP裸机库和RTL8211F配置问题

## 错误原因

在 Zynq 平台使用 Vitis + lwIP 裸机应用并搭配 Realtek RTL8211F PHY 时，会在启动时报告：

```
autonegotiaton complete
phy setup error
phy setup failure init emacps
```

此错误说明：
PHY 已经自协商成功，
但lwIP所使用的Xilinx驱动未能正确读取 RTL8211F 的寄存器配置，
从而无法正确完成链路参数设置。

问题的原因在于 Vitis 自带的 lwIP ps7 以太网驱动并不支持 RTL8211F，
它只支持 RTL8211E，且两个芯片的寄存器定义不同。

因此 lwIP 驱动会误读 PHY 寄存器，导致 `phy_setup_emacps()` 设置失败。

社区早已有补丁修复该问题，但并没有合并进入主线：
[https://github.com/Digilent/embeddedsw/commit/037af984fc9ad4fe067e56976dd0e1815ab02bef](https://github.com/Digilent/embeddedsw/commit/037af984fc9ad4fe067e56976dd0e1815ab02bef)。

网络上有一些旧版本的库修复了这个问题，
但是多是SDK或Vitis Classic版的，
缺少Vitis Unified IDE所需的yaml以及CMake配置，
也没有对于SDT的API的支持，
相比之下直接从最新版lwip库的基础上修改更为方便。

## 修改方法

### 找到Vitis自带的lwIP库

首先从Vitis的安装路径中
`data/embeddedsw/ThirdParty/sw_services/`
目录下找到lwip库，
可以看到有多个版本，
找到最新的一版，
进入版本目录后，检查：

```
data/lwip<version>.yaml
```

如果存在 YAML，说明该版本可被Vitis Unified IDE 识别，
若目录中没有 yaml 文件，则该库无法用于 Unified IDE，不要使用。

将整个库复制出来，
保持原目录结构，
```
lwip_<version>/
    data/
    src/
    cmake/
```

Vitis Unified IDE 只要能扫描到 yaml 文件，就能识别为一个软件仓库。

### 修改驱动源码

路径：

```
src/lwip-2.2.0/contrib/ports/xilinx/netif/xemacpsif_physpeed.c
```

需要修改核心函数：

```
get_Realtek_phy_speed()
```

根据补丁：

[Commit 037af98](https://github.com/Digilent/embeddedsw/commit/037af984fc9ad4fe067e56976dd0e1815ab02bef)

新增对RTL8211F的支持，并修正相关寄存器读取逻辑。

### 在 Vitis Unified IDE 中添加软件仓库

在菜单栏选择：

```
Vitis → Embedded SW Repositories...
```

添加软件仓库（修改后的库的上层目录）并Rescan，
此时重新生成BSP可以看到lwip库有两个路径，
选择本地仓库的路径即可。
此时lwip已经被替换为修改后的版本，
构建完成即可正常驱动 RTL8211F。

## 参考资料

- Xilinx Issue：

   [https://github.com/Xilinx/embeddedsw/issues/255](https://github.com/Xilinx/embeddedsw/issues/255)

- Digilent 修复提交：

   [https://github.com/Digilent/embeddedsw/commit/037af984fc9ad4fe067e56976dd0e1815ab02bef](https://github.com/Digilent/embeddedsw/commit/037af984fc9ad4fe067e56976dd0e1815ab02bef)

- 基于Lemon ZYNQ的PS实验十（同样的问题，但是基于SDK）：

   [http://www.hellofpga.com/index.php/2024/10/07/lemon_zynq_net_test/](http://www.hellofpga.com/index.php/2024/10/07/lemon_zynq_net_test/)