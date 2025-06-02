# AXI-Stream接口

## 数据宽度

尽管AXI-Stream标准没有规定`tdata`的宽度必须为8的倍数，
但是Vivado的ip核一般都是按字节对齐的，
所以还是建议将`tdata`宽度对齐，
特别是有多个并行数据的情况。

```verilog
input wire [(DATA_WIDTH)/8*8-1 : 0] s_axis_tdata
```

两个数据的情况

```verilog
input wire [2*((DATA_WIDTH)/8*8)-1 : 0] s_axis_tdata
```

## 握手与反压

在时钟上升沿，
如果`tready`和`tvalid`同时为高则为握手成功，
此时发生数据传递。

为了保证数据完整性，
AXI-Stream协议规定当`tvalid`拉高后，
在`tready`拉高、握手结束之前，
其他信号应当保持不变，
且`tvalid`不得自行拉低。
`tready`可以根据接收端状态随时拉高或拉低。

注意`tvalid`与`tready`不可过度依赖，
在AXI-Stream协议中，
`tready`可以等待`tvalid`拉高再拉高，
但`tvalid`不可依赖`tready`，
以防止死锁（deadlock）。
本文的样例中`tready`和`tvalid`都是独立的。

在复位状态下，
虽然标准并没有硬性规定`tready`必须为低，
但在一般情况下，
还是应该将`tready`在复位期间置低，
以防止意外握手。

当后级未准备好时，
如果本级进行数据传递，
那么它就需要反压前级，
让前级的数据也保持不动，
直到握手成功才能更新数据。

### Half-Buffer

当寄存器空时只可以进行输入握手，
当寄存器满时只可以进行输出握手。
只能实现50%的吞吐率。

??? example

    ```verilog title="axis_half_buffer.v"
    --8<-- "fpga/pipeline/axis_half_buffer.v"
    ```

### Pre-fetch预取设计

当前数据在被处理的同时，
已经准备好接收下一个数据，
使得输入输出可以同时进行，
实现理论上100%的吞吐率。

然而如果没有额外的存储体的话，
则必须通过组合逻辑反压前级，
让整个流水线在一个时钟周期之内停下。
如果流水线过长或控制逻辑太复杂，
可能会造成时序问题，
不过一般来说不会有什么影响。

??? example

    ```verilog title="axis_prefetch.v"
    --8<-- "fpga/pipeline/axis_prefetch.v"
    ```

### Skid Buffer

当后级无法接收数据时，
使用一个额外的缓冲区存储输入数据，
相当于一个深度为2的最小的FIFO。
这样输出输出间就不再需要组合路径，
但是控制状态机更复杂一些。

相关文章:

- [fpgacpu.ca Pipeline Skid-Buffer](https://fpgacpu.ca/fpga/Pipeline_Skid_Buffer.html);

- [zipcpu.com Skid-Buffer](https://zipcpu.com/blog/2019/05/22/skidbuffer.html)

??? example

    ```verilog title="axis_skid_buffer.v"
    --8<-- "fpga/pipeline/axis_skid_buffer.v"
    ```

### 使用FIFO缓冲

如果不能让流水线的每一级都停下来，
可以在流水线后添加FIFO，
当流水线和FIFO中数据总量即将溢出时，
提前反压前级。

示例代码使用了Vivado的XPM实现FIFO,
使用独立的计数器而非FIFO自带的`prog_full`
是因为FIFO无法得知流水线内的数据数量，
可能会产生空泡，
从而无法达到100%的吞吐率。

??? example

    ```verilog title="axis_fifo_pipeline.v"
    --8<-- "fpga/pipeline/axis_fifo_pipeline.v"
    ```

### 跨级反压

如果对于吞吐率没有严格要求的话，
可以根据FIFO深度和流水线级数计算水线，
配合`prog_full`和门控模块实现跨级反压。

## 控制和同步

`tlast`用于表示一帧数据的结束。

在涉及到数据同步的模块（如计数器）中，
不难想到如果意外发生了数据的丢失或重复，
即使后面的数据是正确的，
也很有可能一直错位下去。
所以即使有些模块(如`fft`)不需要`tlast`也能正常工作，
还是建议加入对`tlast`的检测。

### 门控缓冲级

如果有额外的逻辑控制流水线的启停，
直接在AXI-Stream的握手信号中加入组合逻辑很可能会产生问题，
建议加入一级门控缓冲。

由于门控级可能需要频繁启停，
为了保证吞吐率，
使用ping-pong双缓冲区设计。

此设计确保`m_axis_tvalid`只会在`enable`为高时才拉高。

??? example

    ```verilog title="axis_gating.v"
    --8<-- "fpga/pipeline/axis_gating.v"
    ```

### 循环缓冲区

如果能够接受部分数据的丢失，
或者希望获取即时的数据
（如ADC采样数据），
则可以使用循环缓冲区，
当流水线阻塞时，
新数据覆盖旧数据。

简单的循环缓冲区只用将`tready`一直拉高就可以了，
但是如果数据是按帧发送的，
为了保证数据包的完整性，
需要使用两个缓冲区交替读写。

??? example

    ```verilog title="axis_circular_buffer.v"
    --8<-- "fpga/pipeline/axis_circular_buffer.v"
    ```

## 仿真

### AXI-Stream VIP

可以使用Xilinx官方的
[AXI-Stream VIP](https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/axi-stream-vip.html#tabs-b98a0a51f7-item-fd9e276c42-tab)
进行仿真。

参考这篇博客[MicroZed Chronicles: AXI Stream Verification IP](https://www.adiuvoengineering.com/post/axi-stream-verification-ip),

官方文档[PG277](https://docs.amd.com/v/u/en-US/pg277-axi4stream-vip)的Test Bench一节也有介绍。

一个比较离谱的问题是Vivado会一直显示找不到相应的包，
但是不影响仿真。

可以在此处下载
VIP的完整文档
[xilinx-vip-api-2021-2.zip](https://www.xilinx.com/support/documentation-navigation/see-all-versions.html?xlnxproducttypes=IP%20Cores&xlnxipcoresname=axi-stream-verification-ip)。

### Cocotb

通过
[cocotbext-axi](https://github.com/alexforencich/cocotbext-axi)
扩展可以实现对AXI-Stream的仿真。

`AxiStreamSource`可以驱动主接口，
`AxiStreamSink`可以驱动从接口，
`AxiStreamMonitor`不驱动任何信号，用于监控流量。

??? example

    ```python title="根据名称查找总线"
    from cocotbext.axi import (AxiStreamBus, AxiStreamSource, AxiStreamSink, AxiStreamMonitor)

    source = AxiStreamSource(AxiStreamBus.from_prefix(dut, 's_axis'), dut.aclk, dut.aresetn, reset_active_level=False)
    sink = AxiStreamSink(AxiStreamBus.from_prefix(dut, 'm_axis'), dut.aclk, dut.aresetn, reset_active_level=False)
    monitor = AxiStreamMonitor(AxiStreamBus.from_prefix(dut, 'int_axis'), dut.aclk, dut.aresetn, reset_active_level=False)
    ```

数据的发送和接收都是以`frame`为单位的，
每一帧都以tlast结尾。
帧的容器为`AxiStreamFrame`。
其中`tdata`数据以`bytearray`存储，
对于其他类型的数据应当在发送前进行数据的转换，
Python的位操作基本都以字节为单位，
不如Verilog便利，
在数据转换中要特别注意数据的对齐。
同时注意Verilog的数据向量一般都是小端序的。

??? example

    ```Python title="int数组向bytearray的转换"
    frame_data = bytearray().join(
        [value.to_bytes(width_bytes, byteorder='little', signed=True) for value in values]
    )
    ```

    ```Python title="非整字节宽有符号数转换为int"
    mask = 2**width_bits-1
    value = int.from_bytes(data, byteorder='little', signed=False)
    value &= mask
    if value >= 2**(width_bits - 1):
        value -= 2**width_bits
    ```

    ```Python title="将bytearray以16进制显示"
    print(f"Frame: {frame.tdata.value.hex()}")
    ```

使用`send(frame)`函数发送数据帧，
模块会自动在末尾拉高`tlast`，
`send_nowait`是`send`的非阻塞版本。
注意无论是`send`还是`send_nowait`都只是把数据放入到了发送缓冲区，
如果需要等待仿真中发送握手完成，
可以使用`wait()`函数，
或者在创建`AxiStreamFrame`时传入`tx_complete=Event()`参数。
`write(data)`和`write_nowait(data)`是
`send`和`send_nowait`的别名，
功能完全相同。

使用`recv()`可以接收数据帧，
`recv_nowait()`是`recv()`的非阻塞版本。
`read(count)`或`read_nowait(count)`可以读取指定的字节数，
但会拆散原有的`frame`。
即使不调用接收函数，
模块也会进行握手并将数据存储到缓冲区，
接收函数则是从缓冲区读取数据，
如果接收数据不够则会阻塞。
如果希望等待仿真中数据帧接收完毕，
可以使用`wait(timeout=0, timeout_unit='ns')`。

如果希望控制实际的握手行为，
即`s_axis_tvalid`或`m_axis_tready`的拉高或拉低，
可以使用`set_pause_generator(generator)`，
参数是一个迭代器，
在每个时钟周期更新一次，
如果更新的值为`True`，
则握手暂停。
使用`clear_pause_generator()`可以清除生成器。

???+ warning

    `clear_pause_generator()`仅仅是清除了生成器，
    并不会改变当前的状态。
    如果在清除之前接口处于暂停状态，
    则会一直暂停下去。
    建议传入一个一直为`False`的生成器确保接口正常工作。

    ```Python
    sink.set_pause_generator(iter(lambda: False, None)) 
    # Optional
    await RisingEdge(dut.aclk)
    sink.clear_puase_generator()
    ```
