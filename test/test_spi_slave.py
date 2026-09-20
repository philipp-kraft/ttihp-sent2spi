# SPDX-FileCopyrightText: © 2026 Philipp Kraft
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

CLK_PERIOD_NS = 20  # 50 MHz simulation clock
SCK_HALF_PERIOD_CYCLES = 8  # clock cycles per SPI half-clock (>> synchronizer latency)

ADDR_FRAME_DATA = 0x00
ADDR_CONFIG = 0x01


async def reset(dut, frame_data=0):
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())

    dut.rst_n.value = 0
    dut.cs.value = 1  # idle (active-low cs)
    dut.mosi.value = 0
    dut.sck.value = 0
    dut.frame_data.value = frame_data
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)


async def _clock_bits(dut, value, nbits, sample_miso):
    """Clock nbits of value out on mosi (MSB first), mode-0 SPI. If
    sample_miso, also sample miso each cycle and return the accumulated value."""
    result = 0
    for i in range(nbits - 1, -1, -1):
        dut.mosi.value = (value >> i) & 1
        dut.sck.value = 1
        await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)
        if sample_miso:
            result = (result << 1) | int(dut.miso.value)
        dut.sck.value = 0
        await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)
    return result


async def spi_read(dut, addr):
    """Read a 32-bit register: an 8-bit command byte (rw=0, addr), then 32
    clocks sampling the register's value off miso, MSB first."""
    dut.cs.value = 0
    await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    await _clock_bits(dut, addr & 0x7F, 8, sample_miso=False)
    value = await _clock_bits(dut, 0, 32, sample_miso=True)

    dut.cs.value = 1
    await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    return value


async def spi_write(dut, addr, wdata):
    """Write a 32-bit register: an 8-bit command byte (rw=1, addr), then 32
    clocks of wdata driven onto mosi, MSB first."""
    dut.cs.value = 0
    await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    await _clock_bits(dut, 0x80 | (addr & 0x7F), 8, sample_miso=False)
    await _clock_bits(dut, wdata, 32, sample_miso=False)

    dut.cs.value = 1
    await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)


@cocotb.test()
async def test_reset(dut):
    dut._log.info("Start")

    await reset(dut)

    assert dut.miso.value == 0
    assert dut.data_nibble_count.value == 6, "data_nibble_count should default to 6"
    assert dut.pause_pulse_enable.value == 0, "pause_pulse_enable should default to 0"
    assert dut.crc_check_enable.value == 1, "crc_check_enable should default to 1"


@cocotb.test()
async def test_read_frame_data(dut):
    dut._log.info("Start")

    frame_data = 0x12345678
    await reset(dut, frame_data=frame_data)

    value = await spi_read(dut, ADDR_FRAME_DATA)
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

    await _clock_bits(dut, ADDR_FRAME_DATA, 8, sample_miso=False)

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
    value = await spi_read(dut, ADDR_FRAME_DATA)
    assert value == second_frame, f"expected {second_frame:#010x}, got {value:#010x}"


@cocotb.test()
async def test_config_write_read(dut):
    dut._log.info("Start")

    await reset(dut)

    await spi_write(dut, ADDR_CONFIG, 3)

    value = await spi_read(dut, ADDR_CONFIG)
    assert value == 3, f"expected 3, got {value}"
    assert dut.data_nibble_count.value == 3, "data_nibble_count output didn't update"


@cocotb.test()
async def test_config_write_out_of_range_rejected(dut):
    """data_nibble_count is only valid for 1-6; writes outside that range
    must be ignored rather than corrupting the register."""
    dut._log.info("Start")

    await reset(dut)

    await spi_write(dut, ADDR_CONFIG, 0)
    value = await spi_read(dut, ADDR_CONFIG)
    assert value == 6, f"expected default 6 after rejecting 0, got {value}"

    await spi_write(dut, ADDR_CONFIG, 7)
    value = await spi_read(dut, ADDR_CONFIG)
    assert value == 6, f"expected default 6 after rejecting 7, got {value}"


@cocotb.test()
async def test_config_pause_pulse_bit(dut):
    dut._log.info("Start")

    await reset(dut)

    # bit 3 = pause_pulse_enable, bits [2:0] = data_nibble_count
    await spi_write(dut, ADDR_CONFIG, 0b1011)

    value = await spi_read(dut, ADDR_CONFIG)
    assert value == 0b1011, f"expected 0b1011, got {value:#06b}"
    assert dut.data_nibble_count.value == 3, "data_nibble_count output didn't update"
    assert dut.pause_pulse_enable.value == 1, "pause_pulse_enable output didn't update"

    await spi_write(dut, ADDR_CONFIG, 0b0011)
    value = await spi_read(dut, ADDR_CONFIG)
    assert value == 0b0011, f"expected 0b0011, got {value:#06b}"
    assert dut.pause_pulse_enable.value == 0, "pause_pulse_enable didn't clear"


@cocotb.test()
async def test_config_crc_check_bit(dut):
    dut._log.info("Start")

    await reset(dut)

    # bit 4 = crc_check_enable, bits [2:0] = data_nibble_count; clear crc_check_enable
    await spi_write(dut, ADDR_CONFIG, 0b00110)

    value = await spi_read(dut, ADDR_CONFIG)
    assert value == 0b00110, f"expected 0b00110, got {value:#07b}"
    assert dut.crc_check_enable.value == 0, "crc_check_enable didn't clear"

    # writes are whole-register: re-set it back to enabled
    await spi_write(dut, ADDR_CONFIG, 0b10110)
    value = await spi_read(dut, ADDR_CONFIG)
    assert value == 0b10110, f"expected 0b10110, got {value:#07b}"
    assert dut.crc_check_enable.value == 1, "crc_check_enable didn't re-enable"


@cocotb.test()
async def test_write_frame_data_is_ignored(dut):
    """frame_data is read-only; writing to its address must not change it."""
    dut._log.info("Start")

    frame_data = 0x12345678
    await reset(dut, frame_data=frame_data)

    await spi_write(dut, ADDR_FRAME_DATA, 0xDEADBEEF)

    value = await spi_read(dut, ADDR_FRAME_DATA)
    assert value == frame_data, f"expected {frame_data:#010x}, got {value:#010x}"
