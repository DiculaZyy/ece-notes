import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge, FallingEdge
from cocotbext.axi import AxiStreamSource, AxiStreamSink, AxiStreamBus, AxiStreamFrame
import cocotb.utils
import cocotb_test.simulator
import pytest
import random
import queue
import logging
import os
from enum import Enum
from functools import partial

class TB(object):
    def __init__(self, dut, clk_period_ns=10):
        self.dut = dut
    
        self.width_bytes = len(dut.s_axis_tdata.value) // 8

        self.input_throughput = 1.0
        self.output_throughput = 1.0

        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.INFO)
        self.clk_period_ns = clk_period_ns

        cocotb.start_soon(Clock(dut.aclk, self.clk_period_ns, units="ns").start())

        self.source = AxiStreamSource(AxiStreamBus.from_prefix(dut, "s_axis"), dut.aclk, dut.aresetn, reset_active_level=False)
        self.sink = AxiStreamSink(AxiStreamBus.from_prefix(dut, "m_axis"), dut.aclk, dut.aresetn, reset_active_level=False)

        if hasattr(dut, "enable"):
            self.dut.enable.setimmediatevalue(1)

    def set_input_throughput(self, throughput):
        """Set the input throughput in frames per second"""
        self.input_throughput = throughput
        if throughput < 1.0:
            self.source.set_pause_generator(iter(lambda: random.random() < 1.0 - throughput, None))
        else:
            self.source.set_pause_generator(iter(lambda: False, None))
        
    def set_output_throughput(self, throughput):
        """Set the output throughput in frames per second"""
        self.output_throughput = throughput
        if throughput < 1.0:
            self.sink.set_pause_generator(iter(lambda: random.random() < 1.0 - throughput, None))
        else:
            self.sink.set_pause_generator(iter(lambda: False, None))

    async def wait_for_input_handshake(self):
        event = RisingEdge(self.dut.aclk)
        while True:
            await event
            if self.dut.s_axis_tvalid.value and self.dut.s_axis_tready:
                return cocotb.utils.get_sim_time(units="ns")
    
    async def wait_for_output_handshake(self):
        event = RisingEdge(self.dut.aclk)
        while True:
            await event
            if self.dut.m_axis_tvalid.value and self.dut.m_axis_tready:
                return cocotb.utils.get_sim_time(units="ns")

    async def wait_for_input_pause(self):
        """Wait for the input stream to pause"""
        event = RisingEdge(self.dut.aclk)
        while True:
            await event
            if not self.dut.s_axis_tvalid.value or not self.dut.s_axis_tready.value:
                return cocotb.utils.get_sim_time(units="ns")
    
    async def wait_for_output_pause(self):
        """Wait for the output stream to pause"""
        event = RisingEdge(self.dut.aclk)
        while True:
            await event
            if not self.dut.m_axis_tvalid.value or not self.dut.m_axis_tready.value:
                return cocotb.utils.get_sim_time(units="ns")

    async def reset(self):
        self.dut.aresetn.setimmediatevalue(1)
        await RisingEdge(self.dut.aclk)
        await RisingEdge(self.dut.aclk)
        self.dut.aresetn.value = 0
        await RisingEdge(self.dut.aclk)
        await RisingEdge(self.dut.aclk)
        self.dut.aresetn.value = 1
        await RisingEdge(self.dut.aclk)
        await RisingEdge(self.dut.aclk)

class PipelineMetrics:
    """Class to store and calculate all performance metrics for the pipeline buffer"""
    def __init__(self, tb : TB):
        self.tb = tb
        self.time_out_threshold_ns = 1000  # Time threshold in ns for output hold time
        self.frame_count = 0
        self.total_bytes = 0
        self.frame_queue = queue.Queue()
    
    def send_frame(self, frame):
        """Record a frame sent to the pipeline"""
        self.frame_queue.put(frame)
        self.tb.source.send_nowait(AxiStreamFrame(frame))

    async def receive_frame(self):
        """Record a frame received from the pipeline"""
        if self.frame_queue.empty():
            raise RuntimeError("Received frame without a corresponding sent frame")
        await self.tb.sink.wait(self.time_out_threshold_ns, "ns")
        frame = await self.tb.sink.recv()
        self.frame_count += 1
        self.total_bytes += len(frame)
        expected = self.frame_queue.get()
        if expected != frame.tdata:
            raise ValueError(f"Received frame does not match expected frame:"\
                              f"{expected.hex()} != {frame.tdata.hex()}")


def generate_random_frames(num=1, size=1, width_bytes=4):
    """Generate a list of random frames with the specified size and width in bytes"""
    return [bytes(random.getrandbits(8) for _ in range(size * width_bytes)) for _ in range(num)]


@cocotb.test()
async def run_test_startup_and_recovery(dut):
    tb = TB(dut)

    metrics = PipelineMetrics(tb)

    await tb.reset()

    frames = generate_random_frames(num=16, size=256, width_bytes=tb.width_bytes)

    for frame in frames:
        metrics.send_frame(frame)

    # Test Startup Latency
    start_time = await tb.wait_for_input_handshake()
    tb.log.info(f"Input Start at {start_time} ns")

    end_time = await tb.wait_for_output_handshake()
    tb.log.info(f"Output Start at {end_time} ns")

    start_up_latency = end_time - start_time

    await metrics.receive_frame()

    # Test Output Hold Time
    tb.set_input_throughput(0.0) # Stop input

    start_time = await tb.wait_for_input_pause()
    tb.log.info(f"Input stopped at {start_time} ns")

    end_time = await tb.wait_for_output_pause()
    tb.log.info(f"Output stopped at {end_time} ns")

    output_hold_time = end_time - start_time

    tb.set_input_throughput(1.0)  # Resume input

    await metrics.receive_frame()

    # Test Input Capacity
    tb.set_output_throughput(0.0)

    start_time = await tb.wait_for_output_handshake()
    tb.log.info(f"Output stopped at {start_time} ns")

    end_time = await tb.wait_for_input_pause()
    tb.log.info(f"Input stopped at {end_time} ns")

    input_capacity = end_time - start_time
    tb.set_output_throughput(1.0)

    await metrics.receive_frame()

    while not metrics.frame_queue.empty():
        await metrics.receive_frame()

    tb.log.info(f"==== Startup and Recovery Test Results ====")
    tb.log.info(f"Startup Latency: {start_up_latency} ns")
    tb.log.info(f"Output Hold Time: {output_hold_time} ns")
    tb.log.info(f"Input Capacity: {input_capacity} ns")
    tb.log.info(f"Total Frames Processed: {metrics.frame_count}")
    tb.log.info(f"Total Bytes Processed: {metrics.total_bytes}")
    tb.log.info(f"==============================================")

async def throughput_test(dut, name, input_throughput, output_throughput):
    """Run a throughput test with specified input and output throughput"""
    tb = TB(dut)

    metrics = PipelineMetrics(tb)

    await tb.reset()

    frames = generate_random_frames(num=16, size=256, width_bytes=tb.width_bytes)

    for frame in frames:
        metrics.send_frame(frame)

    tb.set_input_throughput(input_throughput)
    tb.set_output_throughput(output_throughput)

    input_start_time = await tb.wait_for_input_handshake()
    tb.log.info(f"Input Start at {input_start_time} ns")

    output_start_time = await tb.wait_for_output_handshake()
    tb.log.info(f"Output Start at {output_start_time} ns")

    await tb.source.wait()
    input_end_time = cocotb.utils.get_sim_time(units="ns")
    tb.log.info(f"Input End at {input_end_time} ns")

    while not metrics.frame_queue.empty():
        await metrics.receive_frame()
    output_end_time = cocotb.utils.get_sim_time(units="ns")
    tb.log.info(f"Output End at {output_end_time} ns")

    total_time_ns = output_end_time - input_start_time

    ideal_throughput_MBs = (tb.width_bytes / 2**20) / (tb.clk_period_ns / 1e9)

    input_total_time_ns = input_end_time - input_start_time
    input_throughput_MBs = (metrics.total_bytes / 2**20) / (input_total_time_ns / 1e9)
    input_utilization = input_throughput_MBs / ideal_throughput_MBs * 100

    output_total_time_ns = output_end_time - output_start_time
    output_throughput_MBs = (metrics.total_bytes / 2**20) / (output_total_time_ns / 1e9)
    output_utilization = output_throughput_MBs / ideal_throughput_MBs * 100

    tb.log.info(f"==== {name} Throughput Test Results ====")
    tb.log.info(f"Total Time: {total_time_ns} ns")
    tb.log.info(f"Total Frames Processed: {metrics.frame_count}")
    tb.log.info(f"Total Bytes Processed: {metrics.total_bytes}")
    tb.log.info(f"Input Throughput: {input_throughput_MBs:.2f} MB/s")
    tb.log.info(f"Input Utilization: {input_utilization:.2f}%")
    tb.log.info(f"Output Throughput: {output_throughput_MBs:.2f} MB/s")
    tb.log.info(f"Output Utilization: {output_utilization:.2f}%")
    tb.log.info(f"==============================================")

@cocotb.test()
async def run_test_continuous_throughput(dut):
    await throughput_test(dut, "Continuous", 1.0, 1.0)
    
@cocotb.test()
async def run_test_input_limited_throughput(dut):
    await throughput_test(dut, "Input Limited", 0.7, 1.0)

@cocotb.test()
async def run_test_output_limited_throughput(dut):
    await throughput_test(dut, "Output Limited", 1.0, 0.7)

@cocotb.test()
async def run_test_balanced_limited_throughput(dut):
    await throughput_test(dut, "Balanced Limited", 0.7, 0.7)
    
@pytest.mark.parametrize("dut", [
    "axis_half_buffer",
    "axis_prefetch",
    "axis_skid_buffer",
    "axis_fifo_pipeline",
    "axis_gating"
])
def test_pipeline_throughput(dut):
    """Run throughput tests for different pipeline modules"""
    module = os.path.splitext(os.path.basename(__file__))[0]
    toplevel = dut

    verilog_sources = [
        os.path.join(os.path.dirname(__file__), f"{dut}.v"),
    ]

    sim_args = []

    if (dut == "axis_fifo_pipeline"):
        sim_args.extend(["-L","unisims_ver",
                         "-L","unimacro_ver",
                         "-L","secureip",
                         "-L","xpm",
                         f"{toplevel}.glbl"
                        ])

        verilog_sources.append(
            os.path.join(os.path.dirname(__file__), "glbl.v")
        )
        verilog_sources.append(
            os.path.join(os.path.dirname(__file__), "pipeline.v")
        )

    cocotb_test.simulator.run(
        verilog_sources=verilog_sources,
        toplevel=toplevel,
        module=module,
        sim_args=sim_args,
    )