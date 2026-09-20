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

ADDR_FRAME_DATA = 0x00
ADDR_CONFIG = 0x01
ADDR_STATUS = 0x02

CFG_PAUSE_PULSE_ENABLE = 1 << 3
CFG_CRC_CHECK_ENABLE = 1 << 4
CFG_DEFAULT = CFG_CRC_CHECK_ENABLE | 6  # crc checking on, no pause, 6 data nibbles


def sent_crc4(nibbles):
    """SAE J2716 CRC-4: seed 5, poly x^4+x^3+x^2+1 (0x13), over the status
    nibble and the 6 data nibbles. Mirrors crc4_step() in sent_receiver.sv."""
    crc = 5
    for nibble in nibbles:
        crc ^= nibble
        for _ in range(4):
            if crc & 0x8:
                crc = ((crc << 1) ^ 0x13) & 0xF
            else:
                crc = (crc << 1) & 0xF
    return crc


async def send_pulse(dut, period_ticks):
    low_cycles = LOW_TICKS * TICK_CYCLES
    high_cycles = (period_ticks - LOW_TICKS) * TICK_CYCLES

    dut.ui_in.value = 0
    await ClockCycles(dut.clk, low_cycles)
    dut.ui_in.value = 1
    await ClockCycles(dut.clk, high_cycles)


def set_uio_in(dut, cs=1, mosi=0, sck=0):
    dut.uio_in.value = (sck << UIO_SCK) | (mosi << UIO_MOSI) | (cs << UIO_CS)


async def _clock_bits(dut, value, nbits, sample_miso):
    """Clock nbits of value out on mosi (MSB first), mode-0 SPI. If
    sample_miso, also sample miso each cycle and return the accumulated value."""
    result = 0
    for i in range(nbits - 1, -1, -1):
        bit = (value >> i) & 1
        set_uio_in(dut, cs=0, mosi=bit, sck=0)
        set_uio_in(dut, cs=0, mosi=bit, sck=1)
        await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)
        if sample_miso:
            miso = (int(dut.uio_out.value) >> UIO_MISO) & 1
            result = (result << 1) | miso
        set_uio_in(dut, cs=0, mosi=bit, sck=0)
        await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)
    return result


async def spi_read(dut, addr):
    """Read a 32-bit register: an 8-bit command byte (rw=0, addr), then 32
    clocks sampling the register's value off miso, MSB first."""
    set_uio_in(dut, cs=0)
    await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    await _clock_bits(dut, addr & 0x7F, 8, sample_miso=False)
    value = await _clock_bits(dut, 0, 32, sample_miso=True)

    set_uio_in(dut, cs=1)
    await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    return value


async def spi_write(dut, addr, wdata):
    """Write a 32-bit register: an 8-bit command byte (rw=1, addr), then 32
    clocks of wdata driven onto mosi, MSB first."""
    set_uio_in(dut, cs=0)
    await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)

    await _clock_bits(dut, 0x80 | (addr & 0x7F), 8, sample_miso=False)
    await _clock_bits(dut, wdata, 32, sample_miso=False)

    set_uio_in(dut, cs=1)
    await ClockCycles(dut.clk, SCK_HALF_PERIOD_CYCLES)


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

    # 1 status nibble + 6 data nibbles, followed by their computed CRC nibble
    payload = [0x3, 0x1, 0x2, 0xF, 0x0, 0x9, 0x6]
    nibbles = payload + [sent_crc4(payload)]
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

    value = await spi_read(dut, ADDR_FRAME_DATA)
    dut._log.info(f"read {value:#010x}, expected {expected:#010x}")
    assert value == expected, f"expected {expected:#010x}, got {value:#010x}"

    assert int(dut.uo_out.value) == 0b01, f"expected data_valid set, got {int(dut.uo_out.value):#04b}"

    status = await spi_read(dut, ADDR_STATUS)
    assert status == 0b01, f"expected status 0b01 over SPI, got {status:#04b}"


@cocotb.test()
async def test_config_nibble_count(dut):
    """Writing the config register changes how many data nibbles a frame
    needs, exercised end-to-end through the SPI pins and the SENT decoder."""
    dut._log.info("Start")

    await reset(dut)

    value = await spi_read(dut, ADDR_CONFIG)
    assert value == CFG_DEFAULT, f"expected default {CFG_DEFAULT:#07b}, got {value:#07b}"

    await spi_write(dut, ADDR_CONFIG, CFG_CRC_CHECK_ENABLE | 3)
    value = await spi_read(dut, ADDR_CONFIG)
    expected_config = CFG_CRC_CHECK_ENABLE | 3
    assert value == expected_config, f"expected {expected_config:#07b} after write, got {value:#07b}"

    # 1 status nibble + 3 data nibbles, followed by their computed CRC nibble
    payload = [0x3, 0x1, 0x2, 0xF]
    nibbles = payload + [sent_crc4(payload)]
    expected = 0
    for value in nibbles:
        expected = ((expected << 4) | value) & 0xFFFFFFFF

    await send_pulse(dut, 56)
    for value in nibbles:
        await send_pulse(dut, value + 12)
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 20)

    value = await spi_read(dut, ADDR_FRAME_DATA)
    dut._log.info(f"read {value:#010x}, expected {expected:#010x}")
    assert value == expected, f"expected {expected:#010x}, got {value:#010x}"


@cocotb.test()
async def test_crc_error_status(dut):
    """A bad CRC must set data_error on uo_out without setting data_valid, and a
    good frame afterwards must clear data_error and set data_valid."""
    dut._log.info("Start")

    await reset(dut)

    payload = [0x3, 0x1, 0x2, 0xF, 0x0, 0x9, 0x6]
    bad_nibbles = payload + [sent_crc4(payload) ^ 0x1]

    await send_pulse(dut, 56)
    for value in bad_nibbles:
        await send_pulse(dut, value + 12)
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 20)

    assert int(dut.uo_out.value) == 0b10, f"expected data_error set, got {int(dut.uo_out.value):#04b}"

    good_nibbles = payload + [sent_crc4(payload)]
    await send_pulse(dut, 56)
    for value in good_nibbles:
        await send_pulse(dut, value + 12)
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 20)

    assert int(dut.uo_out.value) == 0b01, f"expected data_valid set, got {int(dut.uo_out.value):#04b}"
