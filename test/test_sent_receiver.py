# SPDX-FileCopyrightText: © 2026 Philipp Kraft
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

CLK_PERIOD_NS = 20  # 50 MHz simulation clock
TICK_CYCLES = 150  # clock cycles per SENT tick for this test (roughly 3 us)
LOW_TICKS = 5  # SENT low-pulse width, in ticks


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

    tick_len = dut.i_sent_receiver.tick_len_q.value.integer
    dut._log.info(f"tick_len_q = {tick_len}")
    assert tick_len == TICK_CYCLES, f"expected {TICK_CYCLES}, got {tick_len}"
