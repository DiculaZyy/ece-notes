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
        self.buffer_size = dut.BUFFER_SIZE.value
        self.tid_width_bits = dut.TID_WIDTH.value

        self.input_throughput = 1.0
        self.output_throughput = 1.0

        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.INFO)
        self.clk_period_ns = clk_period_ns

        cocotb.start_soon(Clock(dut.aclk, self.clk_period_ns, units="ns").start())

        self.source = AxiStreamSource(AxiStreamBus.from_prefix(dut, "s_axis"), dut.aclk, dut.aresetn, reset_active_level=False)
        self.sink = AxiStreamSink(AxiStreamBus.from_prefix(dut, "m_axis"), dut.aclk, dut.aresetn, reset_active_level=False)

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
        id = random.randint(0, 2**self.tb.tid_width_bits - 1)
        self.frame_queue.put((frame, id))
        self.tb.source.send_nowait(AxiStreamFrame(frame, tid=id))

    async def receive_frame(self, allow_overflow=False):
        """Record a frame received from the pipeline"""
        if self.frame_queue.empty():
            raise RuntimeError("Received frame without a corresponding sent frame")
        await self.tb.sink.wait(self.time_out_threshold_ns, "ns")
        frame = await self.tb.sink.recv()
        self.frame_count += 1
        self.total_bytes += len(frame)
        [exp_data, exp_id] = self.frame_queue.get()
        if exp_data != frame.tdata:
            if allow_overflow:
                if len(exp_data) > len(frame.tdata):
                    self.tb.log.info(f"Overflow detected: expected {len(exp_data)} bytes, received {len(frame.tdata)} bytes")
                exp_data = exp_data[:len(frame.tdata) - self.tb.width_bytes]  # Truncate expected data to match received frame size
                data = frame.tdata[:len(exp_data)]
                if exp_data != data:
                    raise ValueError(f"Received frame does not match expected frame:"\
                                f"{exp_data.hex()} != {data.hex()}")
            else:
                raise ValueError(f"Received frame does not match expected frame:"\
                                f"{exp_data.hex()} != {frame.tdata.hex()}")
        
        if type(frame.tid) is list:
            for id in frame.tid:
                if id != exp_id:
                    raise ValueError(f"Received frame ID {id} does not match expected ID {exp_id}")
        else:
            if frame.tid != exp_id:
                raise ValueError(f"Received frame ID {frame.tid} does not match expected ID {exp_id}")


def generate_random_frames(num=1, size=1, width_bytes=4):
    """Generate a list of random frames with the specified size and width in bytes"""
    return [bytes(random.getrandbits(8) for _ in range(size * width_bytes)) for _ in range(num)]



@cocotb.test()
async def run_test_continuous(dut):
    tb = TB(dut)
    metrics = PipelineMetrics(tb)

    # Reset the DUT
    await tb.reset()

    # Set input and output throughput
    tb.set_input_throughput(1.0)
    tb.set_output_throughput(1.0)

    # Generate random frames
    frames = generate_random_frames(num=100, size=tb.buffer_size, width_bytes=tb.width_bytes)

    # Send frames to the pipeline
    for frame in frames:
        metrics.send_frame(frame)

    # Receive frames from the pipeline
    for _ in range(len(frames)):
        await metrics.receive_frame(False)

@cocotb.test()
async def run_test_small_frames(dut):
    tb = TB(dut)
    metrics = PipelineMetrics(tb)

    # Reset the DUT
    await tb.reset()

    # Set input and output throughput
    tb.set_input_throughput(1.0)
    tb.set_output_throughput(1.0)

    # Generate random frames
    for _ in range(10):
        frames = generate_random_frames(num=10, size=random.randint(2, tb.buffer_size), width_bytes=tb.width_bytes)

        # Send frames to the pipeline
        for frame in frames:
            metrics.send_frame(frame)

        # Receive frames from the pipeline
        for _ in range(len(frames)):
            await metrics.receive_frame(False)

@cocotb.test()
async def run_test_signal_cycle_frames(dut):
    tb = TB(dut)
    metrics = PipelineMetrics(tb)

    # Reset the DUT
    await tb.reset()

    # Set input and output throughput
    tb.set_input_throughput(1.0)
    tb.set_output_throughput(1.0)

    send_frame_num = 1000

    # Generate random frames
    frames = generate_random_frames(num=send_frame_num, size=1, width_bytes=tb.width_bytes)

    for frame in frames:
        id = random.randint(0, 2**tb.tid_width_bits - 1)
        tb.source.send_nowait(AxiStreamFrame(frame, tid=id))

    await tb.sink.wait(1000, "ns")

    recv_frame_num = 0

    while True:
        await tb.sink.wait(1000, "ns")
        if tb.sink.empty():
            tb.log.info("No more frames to receive, exiting")
            break
        frame = await tb.sink.recv()
        recv_frame_num += 1
        if type(frame.tid) is list:
            for id in frame.tid:
                if id != frame.tid[0]:
                    raise ValueError(f"Received frame ID {id} does not the same ID {frame.tid[0]}")

    tb.log.info(f"Sent {send_frame_num} frames, received {recv_frame_num} frames")
    tb.log.info(f"Loss Rate: {(send_frame_num - recv_frame_num) / send_frame_num * 100}%")

@cocotb.test()
async def run_test_overflow(dut):
    tb = TB(dut)
    metrics = PipelineMetrics(tb)

    # Reset the DUT
    await tb.reset()

    # Set input and output throughput
    tb.set_input_throughput(1.0)
    tb.set_output_throughput(1.0)

    # Generate random frames
    for _ in range(10):
        frames = generate_random_frames(num=10, size=random.randint(1, 5*tb.buffer_size), width_bytes=tb.width_bytes)

        # Send frames to the pipeline
        for frame in frames:
            metrics.send_frame(frame)

        # Receive frames from the pipeline
        for _ in range(len(frames)):
            await metrics.receive_frame(True)

@cocotb.test()
async def run_test_pause(dut):
    tb = TB(dut)

    # Reset the DUT
    await tb.reset()

    # Set input and output throughput
    tb.set_input_throughput(0.8)
    tb.set_output_throughput(0.3)

    send_frame_num = 1000

    # Generate random frames
    frames = generate_random_frames(num=send_frame_num, size=tb.buffer_size, width_bytes=tb.width_bytes)

    for frame in frames:
        id = random.randint(0, 2**tb.tid_width_bits - 1)
        tb.source.send_nowait(AxiStreamFrame(frame, tid=id))

    await tb.sink.wait(1000, "ns")

    recv_frame_num = 0

    while True:
        await tb.sink.wait(1000, "ns")
        if tb.sink.empty():
            tb.log.info("No more frames to receive, exiting")
            break
        frame = await tb.sink.recv()
        recv_frame_num += 1
        if type(frame.tid) is list:
            for id in frame.tid:
                if id != frame.tid[0]:
                    raise ValueError(f"Received frame ID {id} does not the same ID {frame.tid[0]}")

    tb.log.info(f"Sent {send_frame_num} frames, received {recv_frame_num} frames")
    tb.log.info(f"Loss Rate: {(send_frame_num - recv_frame_num) / send_frame_num * 100}%")

def test_circular_buffer():
    """Run the test suite for the circular buffer"""
    dut = "axis_circular_buffer"
    module = os.path.splitext(os.path.basename(__file__))[0]
    toplevel = dut

    verilog_sources = [
        os.path.join(os.path.dirname(__file__), f"{dut}.v"),
    ]

    cocotb_test.simulator.run(
        verilog_sources=verilog_sources,
        toplevel=toplevel,
        module=module,
    )