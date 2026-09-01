# SPDX-FileCopyrightText: © 2026 Philipp Kraft
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

CLK_PERIOD_NS = 20  # 50 MHz simulation clock
TICK_CYCLES = 150  # clock cycles per SENT tick for this test (roughly 3 us)
LOW_TICKS = 5  # SENT low-pulse width, in ticks
SCK_HALF_PERIOD_CYCLES = 8  # clock cycles per SPI half-clock (>> synchronizer latency)

UIO_CS = 0
UIO_MOSI = 1
UIO_MISO = 2
UIO_SCK = 3


async def send_pulse(dut, period_ticks):
    low_cycles = LOW_TICKS * TICK_CYCLES
    high_cycles = (period_ticks - LOW_TICKS) * TICK_CYCLES

    dut.ui_in.value = 0
    await ClockCycles(dut.clk, low_cycles)
    dut.ui_in.value = 1
    await ClockCycles(dut.clk, high_cycles)


def set_uio_in(dut, cs=1, mosi=0, sck=0):
    dut.uio_in.value = (sck << UIO_SCK) | (mosi << UIO_MOSI) | (cs << UIO_CS)


async def spi_read(dut, nbits=32):
    """Drive an SPI mode-0 read transaction (cs low, MSB first) and return the
    integer value sampled on the miso bit of uio_out."""
    set_uio_in(dut, cs=0)
    await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    value = 0
    for _ in range(nbits):
        set_uio_in(dut, cs=0, sck=1)
        await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)
        miso = (int(dut.uio_out.value) >> UIO_MISO) & 1
        value = (value << 1) | miso
        set_uio_in(dut, cs=0, sck=0)
        await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    set_uio_in(dut, cs=1)
    await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    return value


async def reset(dut):
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 1  # SENT idles high
    set_uio_in(dut)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)


@cocotb.test()
async def test_reset(dut):
    dut._log.info("Start")

    await reset(dut)

    assert int(dut.uo_out.value) == 0
    assert int(dut.uio_oe.value) == 0b00000100


@cocotb.test()
async def test_sent_to_spi(dut):
    """Drive a full SENT frame on ui_in[0] and read the decoded value back over
    the SPI pins, exercising the complete sent2spi data path at the chip level."""
    dut._log.info("Start")

    await reset(dut)

    # 1 status nibble + 6 data nibbles + 1 crc nibble
    nibbles = [0x3, 0x1, 0x2, 0xF, 0x0, 0x9, 0x6, 0x0]
    expected = 0
    for value in nibbles:
        expected = ((expected << 4) | value) & 0xFFFFFFFF

    # Sync pulse, then one back-to-back pulse per nibble value
    await send_pulse(dut, 56)
    for value in nibbles:
        await send_pulse(dut, value + 12)

    # One more falling edge to close out the last nibble's pulse, then give
    # the FSM a few cycles to latch frame_data (CRC check + register stage).
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 20)

    value = await spi_read(dut)
    dut._log.info(f"read {value:#010x}, expected {expected:#010x}")
    assert value == expected, f"expected {expected:#010x}, got {value:#010x}"
