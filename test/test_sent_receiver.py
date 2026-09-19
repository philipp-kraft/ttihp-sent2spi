# SPDX-FileCopyrightText: © 2026 Philipp Kraft
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

CLK_PERIOD_NS = 20  # 50 MHz simulation clock
TICK_CYCLES = 150  # clock cycles per SENT tick for this test (roughly 3 us)
LOW_TICKS = 5  # SENT low-pulse width, in ticks


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

    dut.sent_in.value = 0
    await ClockCycles(dut.clk, low_cycles)
    dut.sent_in.value = 1
    await ClockCycles(dut.clk, high_cycles)


@cocotb.test()
async def test_reset(dut):
    dut._log.info("Start")

    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())

    dut.rst_n.value = 0
    dut.sent_in.value = 1  # SENT idles high
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    assert dut.frame_valid.value == 0
    assert dut.frame_error.value == 0

    await ClockCycles(dut.clk, 50)


@cocotb.test()
async def test_tick_calibration(dut):
    dut._log.info("Start")

    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())

    dut.rst_n.value = 0
    dut.sent_in.value = 1  # SENT idles high
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    # Drive one full sync pulse (56 ticks) and then start the next pulse
    await send_pulse(dut, 56)
    dut.sent_in.value = 0

    await ClockCycles(dut.clk, 20)

    tick_len = dut.i_sent_receiver.tick_len_q.value.to_unsigned()
    dut._log.info(f"tick_len_q = {tick_len}")
    assert tick_len == TICK_CYCLES, f"expected {TICK_CYCLES}, got {tick_len}"

    await ClockCycles(dut.clk, 50)


@cocotb.test()
async def test_nibble_decode(dut):
    dut._log.info("Start")

    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())

    dut.rst_n.value = 0
    dut.sent_in.value = 1  # SENT idles high
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    # 1 status nibble + 6 data nibbles, followed by their computed CRC nibble
    payload = [0x3, 0x1, 0x2, 0xF, 0x0, 0x9, 0x6]
    nibbles = payload + [sent_crc4(payload)]

    # Sync pulse, then one back-to-back pulse per nibble value
    await send_pulse(dut, 56)
    for value in nibbles:
        await send_pulse(dut, value + 12)

    # One more falling edge to close out the last nibble's pulse
    dut.sent_in.value = 0

    # frame_valid is a one-cycle pulse, so poll for it cycle-by-cycle
    # instead of waiting a fixed number of cycles and sampling once.
    for _ in range(50):
        await RisingEdge(dut.clk)
        if dut.frame_valid.value == 1:
            break
    else:
        assert False, "frame_valid never pulsed"

    assert dut.frame_error.value == 0, "frame_error asserted unexpectedly"

    expected = 0
    for value in nibbles:
        expected = ((expected << 4) | value) & 0xFFFFFFFF

    frame_data = dut.frame_data.value.to_unsigned()
    dut._log.info(f"frame_data = {frame_data:#010x}, expected = {expected:#010x}")
    assert frame_data == expected, f"expected {expected:#010x}, got {frame_data:#010x}"

    await ClockCycles(dut.clk, 50)


@cocotb.test()
async def test_crc_error(dut):
    dut._log.info("Start")

    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())

    dut.rst_n.value = 0
    dut.sent_in.value = 1  # SENT idles high
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    # Same payload as test_nibble_decode, but with the CRC nibble corrupted.
    payload = [0x3, 0x1, 0x2, 0xF, 0x0, 0x9, 0x6]
    good_crc = sent_crc4(payload)
    bad_crc = good_crc ^ 0x1
    nibbles = payload + [bad_crc]

    await send_pulse(dut, 56)
    for value in nibbles:
        await send_pulse(dut, value + 12)
    dut.sent_in.value = 0

    for _ in range(50):
        await RisingEdge(dut.clk)
        if dut.frame_error.value == 1:
            break
    else:
        assert False, "frame_error never pulsed"

    assert dut.frame_valid.value == 0, "frame_valid asserted on a bad CRC"
    assert dut.frame_data.value.to_unsigned() == 0, "frame_data updated on a bad CRC"

    # The FSM must recover and resync on the very next pulse rather than
    # getting stuck, so a good frame right after a bad one still decodes.
    payload2 = [0x1, 0x2, 0x3, 0x4, 0x5, 0x6]
    nibbles2 = [0x0] + payload2
    nibbles2.append(sent_crc4(nibbles2))

    await send_pulse(dut, 56)
    for value in nibbles2:
        await send_pulse(dut, value + 12)
    dut.sent_in.value = 0

    for _ in range(50):
        await RisingEdge(dut.clk)
        if dut.frame_valid.value == 1:
            break
    else:
        assert False, "frame_valid never pulsed after recovering from a CRC error"

    expected = 0
    for value in nibbles2:
        expected = ((expected << 4) | value) & 0xFFFFFFFF

    frame_data = dut.frame_data.value.to_unsigned()
    assert frame_data == expected, f"expected {expected:#010x}, got {frame_data:#010x}"

    await ClockCycles(dut.clk, 50)
