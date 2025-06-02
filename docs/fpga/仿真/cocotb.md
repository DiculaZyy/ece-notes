# Cocotb

[Cocotb](https://github.com/cocotb/cocotb)
是一个使用Python进行仿真的框架。

官方文档: [https://docs.cocotb.org/en/stable/](https://docs.cocotb.org/en/stable/)

## 基础使用

Cocotb使用
[协程(Coroutines)](https://docs.python.org/3/library/asyncio-task.html#coroutine)
实现测试的并发控制。

可以通过`cocotb.test()`注册测试函数，
测试函数是一个协程，
需要添加`async`关键字。
一个文件可以有多个测试函数，
在测试中将会依次执行。

待测模块将会通过参数
`dut`(Design Under Test)
传入函数。

```python
import cocotb

@cocotb.test()
async def my_test(dut):
    pass
```

可以直接使用`.`来访问设计内部的信号，
如果需要获取或修改值，
则需要使用`.value`

通过`async def`可以定义新的协程并被测试调用，
使用`await`可以等待协程执行完毕。
通过`cocotb.start_soon()`可以启动另一个协程同时运行，
并返回一个`cocotb.task`对象，
可以通过`await`等待其执行完毕。

??? example

    ```python
    async def reset(clk, rst_n):
        rst_n.value = 0
        await Timer(20, units="ns")
        rst_n.value = 1
        await RisingEdge(clk)

    async def background_task():
        await Timer(100, units='ns')

    @cocotb.test()
    async def my_test(dut):
        cocotb.start_soon(Clock(dut.clk, 1, units='ns').start())

        task = cocotb.start_soon(background_task()

        await reset(dut.clk, dut.rst_n)

        await task
    ```

可以通过Makefile配置cocotb

??? example

    ```Makefile
    SIM ?= modelsim
    WAVES ?= 1
    TOPLEVEL_LANG ?= verilog

    VERILOG_SOURCES += $(PWD)/my_design.v

    TOPLEVEL = my_design

    MODULE ?= my_test

    SIM_CMD_SUFFIX := 2>&1 | tee sim.log

    include $(shell cocotb-config --makefiles)/Makefile.sim
    ```

更多配置参数参考
[Build options and Environment Variables](https://docs.cocotb.org/en/stable/building.html)

在默认状态下仿真是在命令行中执行的，
如果希望打开GUI可以配置`GUI=1`，
或者可以配置`WAVES=1`，
在仿真结束后查看波形。
如使用Modelsim可以执行：

```shell
vsim -view vsim.wlf -do "add wave -noupdate /my_design/*"
```

## 和Vivado联动

尽管Vivado并不直接支持Cocotb的仿真，
但是Vivado可以使用第三方的仿真器，
从而间接地实现Cocotb对Vivado的ip核的仿真。
这里以Modelsim为例。

首先需要配置好仿真器并编译ip核，
接着可以通过Vivado的
[导出仿真](https://docs.amd.com/r/zh-CN/ug900-vivado-logic-simulation/%E5%AF%BC%E5%87%BA%E4%BB%BF%E7%9C%9F%E6%96%87%E4%BB%B6%E5%92%8C%E8%84%9A%E6%9C%AC)
功能收集仿真需要的文件和脚本。

其中`modelsim.ini`文件是各种库的路径，
需要放到仿真目录下。
`gldl.v`是全局复位模块，
也需要添加到工程中，
该模块也可以在`$(XILINX_VIVADO)/data/verilog/src/glbl.v`中找到。

打开`compile.do`文件，
其中的`vlog`命令包含了仿真所需要编译的所有文件，
需要添加到Makefile中。
而`xil_defaultlib`是Vivado为仿真创建的库，
并不是必须的，
在Cocotb中一般是`work`。

打开`simulate.do`文件，
其中的`vsim`的`-L`参数包括了所有仿真需要连接的库，
也需要添加到Makefile中。

??? example

    假设Vivado提供的脚本如下:

    === "compile.do"

        ```tcl
        vlib modelsim_lib/work
        vlib modelsim_lib/msim

        vlib modelsim_lib/msim/xil_defaultlib

        vmap xil_defaultlib modelsim_lib/msim/xil_defaultlib

        vlog -work xil_defaultlib -64 -incr -mfcu  \
        "srcs/sources_1/imports/pipeline/pipeline.v" \
        "srcs/sources_1/imports/pipeline/axis_fifo_pipeline.v" \


        vlog -work xil_defaultlib \
        "glbl.v"
        ```

    === "simulate.do"

        ```tcl
        onbreak {quit -f}
        onerror {quit -f}

        vsim -voptargs="+acc"  -L xil_defaultlib -L unisims_ver -L unimacro_ver -L secureip -L xpm -lib xil_defaultlib xil_defaultlib.axis_fifo_pipeline xil_defaultlib.glbl

        set NumericStdNoWarnings 1
        set StdArithNoWarnings 1

        do {wave.do}

        view wave
        view structure
        view signals

        do {axis_fifo_pipeline.udo}

        run 1000ns

        quit -force
        ```

    则可以在Makefile中添加:

    ```Makefile
    VERILOG_SOURCES += $(PWD)/pipeline.v
    VERILOG_SOURCES += $(XILINX_VIVADO)/data/verilog/src/glbl.v

    VSIM_ARGS += -L unisims_ver -L unimacro_ver -L secureip -L xpm work.glbl
    ```

未来也许可以通过脚本自动实现这一过程。

## 使用cocotb-test

使用Makefile配置仿真仍然有诸多不便，
比如说无法一次性测试多个模块，
无法改变参数等，
可以使用
[cocotb-test](https://github.com/themperek/cocotb-test)
实现通过Python执行仿真。

cocotb-test基于[Pytest](https://docs.pytest.org/en/stable/)框架。
pytest会自动查找以`test_`开头的文件运行测试，
测试的函数一般也以`test_`开头。
使用`cocotb_test.simulator.run`函数运行`cocotb`测试，
参数和Makefile类似，
但是`SIM`和`WAVES`需要通过环境变量指定，
详细信息见[Arguments for `simulator.run`](https://github.com/themperek/cocotb-test?tab=readme-ov-file#arguments-for-simulatorrun)

运用pytest的`mark.paramtrize`可以一次性传入多组参数，
实现一次性运行多个测试。

在安装了[pytest-xdist](https://pypi.org/project/pytest-xdist/)之后，
可以实现并行运行多个测试，
提高仿真速度。

??? example

    通过`product`函数生成多组参数，
    并指定本文件作为testbench。

    ```Python title="test_dff.py"
    import cocotb
    import cocotb_test.simulator
    import pytest
    from itertools import product
    import os

    @cocotb.test()
    async def run_test_dff(dut):
        pass

    @pytest.mark.parameterize("A, B",
        #[(0, 0), (0, 1), ...]
        list(product(
            [0, 1, 2], # A
            [0, 1, 2], # B
        ))
    )
    def test_dff(A, B):
        module = os.path.splitext(os.path.basename(__file__))[0]
        dut = "dff"
        toplevel = dut

        verilog_sources = [
            os.path.join(os.path.dirname(__file__), f"{dut}.v"),
        ]

        parameters = {
            'A': A,
            'B': B
        }

        cocotb_test.simulator.run(
            verilog_sources=verilog_sources,
            toplevel=toplevel,
            module=module,
            parameters=parameters,
        )
    ```

    指定仿真器并设置8组并行仿真

    ```shell
    SIM=modelsim WAVES=1 pytest -n 8 -o log_cli=True test_dff.py
    ```

cocotb-test同样可以和Vivado联动，
但是在配置上和Makefile有一些不同。
`vsim`的参数通过`sim_args`指定，
而且以空格分隔的参数必须分为`list`的不同项，
否则会提示`Unknown option`，
此外编译的源文件所在的libaray默认不再是`work`，
而是`toplevel`的名称。

??? example

    对于上例的额外选项可以这样配置：

    ```Python
    sim_args = ["-L","unisims_ver",
                "-L","unimacro_ver",
                "-L","secureip",
                "-L","xpm",
                f"{toplevel}.glbl"
            ]

    verilog_sources.append(
        os.path.join(os.path.dirname(__file__), "glbl.v")
    )
    verilog_sources.append(
        os.path.join(os.path.dirname(__file__), "pipeline.v")
    )
    ```

## Cocotb中的时间线

可以参考这篇文章[cocotb_primer/timeline](https://github.com/opensmartnic/cocotb_primer/blob/master/timeline.md)

一般来说，信号的赋值可以在等待时钟边沿后进行，
如果要读取值，则需要等待`ReadOnly`。

```Python
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge, ReadOnly

async def set_and_check(dut):
    while True:
        await RisingEdge(dut.aclk) # Wait for clock edge
        dut.write_bus.value = ...
        await ReadOnly() # Ensure all signals are updated
        assert dut.read_bus.value == ...
```
