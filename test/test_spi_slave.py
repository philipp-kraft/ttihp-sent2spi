# SPDX-FileCopyrightText: © 2026 Philipp Kraft
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

CLK_PERIOD_NS = 20  # 50 MHz simulation clock
SCK_HALF_PERIOD_CYCLES = 8  # clock cycles per SPI half-clock (>> synchronizer latency)


async def reset(dut, frame_data=0, frame_valid=0, frame_error=0):
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())

    dut.rst_n.value = 0
    dut.cs.value = 1  # idle (active-low cs)
    dut.mosi.value = 0
    dut.sck.value = 0
    dut.frame_data.value = frame_data
    dut.frame_valid.value = frame_valid
    dut.frame_error.value = frame_error
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)


async def spi_read(dut, nbits=32):
    """Drive an SPI mode-0 read transaction (cs low, MSB first) and return the
    integer value sampled on miso, one bit per sck cycle."""
    dut.cs.value = 0
    await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    value = 0
    for _ in range(nbits):
        dut.sck.value = 1
        await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)
        value = (value << 1) | int(dut.miso.value)
        dut.sck.value = 0
        await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    dut.cs.value = 1
    await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    return value


@cocotb.test()
async def test_reset(dut):
    dut._log.info("Start")

    await reset(dut)

    assert dut.miso.value == 0


@cocotb.test()
async def test_read_frame_data(dut):
    dut._log.info("Start")

    frame_data = 0x12345678
    await reset(dut, frame_data=frame_data)

    value = await spi_read(dut)
    dut._log.info(f"read {value:#010x}")
    assert value == frame_data, f"expected {frame_data:#010x}, got {value:#010x}"


@cocotb.test()
async def test_frame_data_frozen_during_transfer(dut):
    """frame_data changing mid-transfer must not corrupt the word being shifted out."""
    dut._log.info("Start")

    first_frame = 0xAAAAAAAA
    second_frame = 0x55555555
    await reset(dut, frame_data=first_frame)

    dut.cs.value = 0
    await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    value = 0
    for i in range(32):
        dut.sck.value = 1
        await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)
        value = (value << 1) | int(dut.miso.value)
        dut.sck.value = 0
        if i == 15:
            dut.frame_data.value = second_frame
        await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    dut.cs.value = 1
    await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    assert value == first_frame, f"expected {first_frame:#010x}, got {value:#010x}"

    # once idle again, the slave should pick up the new frame
    value = await spi_read(dut)
    assert value == second_frame, f"expected {second_frame:#010x}, got {value:#010x}"
