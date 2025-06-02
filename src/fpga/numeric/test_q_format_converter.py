import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, RisingEdge, FallingEdge
from cocotbext.axi import AxiStreamSource, AxiStreamSink, AxiStreamBus, AxiStreamFrame
import cocotb_test.simulator
import pytest
from itertools import product
import random
import os
import math

# --8<-- [start:metrics]
class QFormatMetrics:
    def __init__(self, M = 1, N = 1, allow_overflow = False):
        self.M = M
        self.N = N
        self.allow_overflow = allow_overflow
   
    def to_fixed_point(self, value : float):
        if not self.allow_overflow:
            if value > 2**self.M - 2**(-self.N) :
                return 2**(self.M+self.N) - 1
            elif value < -2**self.M:
                return -2**(self.M+self.N)
        if value >= 0:
            value = value % 2**self.M
        else:
            value = value % 2**self.M - 2**self.M
        return math.floor(value * (2**self.N))
 
    
    def to_float(self, data : int):
        return data / (2**self.N)
# --8<-- [end:metrics]

@cocotb.test()
async def q_format_converter_tb(dut):
    # Create a clock
    cocotb.start_soon(Clock(dut.aclk, 10, units='ns').start())

    # Create AXI Stream interfaces
    source = AxiStreamSource(AxiStreamBus.from_prefix(dut, 's_axis'), dut.aclk, dut.aresetn, reset_active_level=False)
    sink = AxiStreamSink(AxiStreamBus.from_prefix(dut, 'm_axis'), dut.aclk, dut.aresetn, reset_active_level=False)

    # Set up the Pause generators to simulate random pauses in the stream
    source.set_pause_generator(iter(lambda: random.random() < 0.1, None))
    sink.set_pause_generator(iter(lambda: random.random() < 0.1, None))

    # Reset DUT
    dut.aresetn.value = 0
    await Timer(20, units='ns')
    dut.aresetn.value = 1

    # Define Q format metrics
    q_in = QFormatMetrics(M=dut.M_IN.value, N=dut.N_IN.value, allow_overflow=False)
    q_out = QFormatMetrics(M=dut.M_OUT.value, N=dut.N_OUT.value, allow_overflow=dut.ALLOW_OVERFLOW.value)

    # Generate test data
    min_value = -2**(dut.M_IN.value + dut.N_IN.value)
    max_value = 2**(dut.M_IN.value + dut.N_IN.value) - 1
    test_data = list(range(min_value, max_value + 1))

    # Randomly divide test data into frames
    random.shuffle(test_data)
    frames = []
    while test_data:
        frame_size = random.randint(1, 10)  # Random frame size between 1 and 10
        frame_data = test_data[:frame_size]
        test_data = test_data[frame_size:]
        frames.append(frame_data)

    input_data_width_bytes = len(dut.s_axis_tdata.value) // 8
    output_data_width_bytes = len(dut.m_axis_tdata.value) // 8

    # Send frames and verify output
    for frame in frames:
        # Send frame
        send_frame = bytearray().join([value.to_bytes(input_data_width_bytes, byteorder='little', signed=True) for value in frame])
        await source.send(AxiStreamFrame(send_frame))

        # Receive and verify frame
        received_frame = await sink.recv()

        # Compare received data with expected data
        expected_data = [q_out.to_fixed_point(q_in.to_float(value)) for value in frame]
        for i in range(len(expected_data)):
            send_value = frame[i]
            send_data = send_frame[i * input_data_width_bytes:(i + 1) * input_data_width_bytes]
            received_data = received_frame.tdata[i * output_data_width_bytes:(i + 1) * output_data_width_bytes]
            received_value = int.from_bytes(received_data, byteorder='little', signed=False)
            if received_value >= 2**(dut.M_OUT.value + dut.N_OUT.value):
                received_value -= 2**(dut.M_OUT.value + dut.N_OUT.value + 1)
            expected_value = expected_data[i]
            assert received_value == expected_value, f"Mismatch at value {send_value}({send_data.hex()}): expected {expected_value}, got {received_value}({received_data.hex()})"

@pytest.mark.parametrize("M_IN,N_IN,M_OUT,N_OUT,ALLOW_OVERFLOW",
    list(product(
        [0, 3, 7],  # M_IN
        [0, 3, 7],  # N_IN
        [0, 3, 7],  # M_OUT
        [0, 3, 7],  # N_OUT
        [0, 1]  # ALLOW_OVERFLOW
    ))
)
def test_q_format_converter(M_IN, N_IN, M_OUT, N_OUT, ALLOW_OVERFLOW):
    module = os.path.splitext(os.path.basename(__file__))[0]
    dut = "q_format_converter"
    toplevel = dut

    verilog_sources = [
        os.path.join(os.path.dirname(__file__), f"{dut}.v"),
    ]

    parameters = {
        'M_IN': M_IN,
        'N_IN': N_IN,
        'M_OUT': M_OUT,
        'N_OUT': N_OUT,
        'ALLOW_OVERFLOW': ALLOW_OVERFLOW
    }

    cocotb_test.simulator.run(
        verilog_sources=verilog_sources,
        toplevel=toplevel,
        module=module,
        parameters=parameters,
    )
