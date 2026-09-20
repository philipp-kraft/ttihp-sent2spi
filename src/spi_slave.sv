/*
 * Copyright (c) 2026 Philipp Kraft
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module spi_slave (
    input logic clk,
    input logic rst_n,

    input logic [31:0] frame_data,
    input logic        data_valid,
    input logic        data_error,

    input  logic cs,
    input  logic mosi,
    output logic miso,
    input  logic sck,

    output logic [2:0] data_nibble_count,
    output logic       pause_pulse_enable,
    output logic       crc_check_enable
);

  // Every transaction is a command byte (bit 7 = write, bits 6:0 = 7-bit
  // register address), MSB first, followed by a 32-bit data word MSB first.
  localparam logic [6:0] ADDR_FRAME_DATA = 7'h00;  // read-only
  // read/write: bits [2:0] = data_nibble_count, bit [3] = pause_pulse_enable,
  // bit [4] = crc_check_enable
  localparam logic [6:0] ADDR_CONFIG = 7'h01;
  localparam logic [6:0] ADDR_STATUS = 7'h02;  // read-only: bit 0 = data_valid, bit 1 = data_error
  localparam logic [2:0] NIBBLE_COUNT_DEFAULT = 3'd6;

  // ------------------------------------------------------------------
  // Input synchronizer
  // ------------------------------------------------------------------
  logic cs_sync, mosi_sync, sck_sync;

  sync2ff i_sync_cs (
      .clk(clk),
      .rst_n(rst_n),
      .d(cs),
      .q(cs_sync)
  );

  sync2ff i_sync_mosi (
      .clk(clk),
      .rst_n(rst_n),
      .d(mosi),
      .q(mosi_sync)
  );

  sync2ff i_sync_sck (
      .clk(clk),
      .rst_n(rst_n),
      .d(sck),
      .q(sck_sync)
  );

  // ------------------------------------------------------------------
  // SCK edge detection
  // ------------------------------------------------------------------
  logic sck_sync_prev;
  logic sck_rising;
  logic sck_falling;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      sck_sync_prev <= 1'b0;
    end else begin
      sck_sync_prev <= sck_sync;
    end
  end

  assign sck_rising  = sck_sync & !sck_sync_prev;
  assign sck_falling = !sck_sync & sck_sync_prev;

  logic cs_active;
  assign cs_active = !cs_sync;

  // ------------------------------------------------------------------
  // Bit counter: 0-7 is the command byte, 8-39 is the 32-bit data word
  // ------------------------------------------------------------------
  logic [5:0] bit_cnt_q;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      bit_cnt_q <= '0;
    end else if (!cs_active) begin
      bit_cnt_q <= '0;
    end else if (sck_rising) begin
      bit_cnt_q <= bit_cnt_q + 1'b1;
    end
  end

  // ------------------------------------------------------------------
  // MOSI capture: command byte, then write data
  // ------------------------------------------------------------------
  logic [7:0] cmd_reg_q;
  logic [31:0] wdata_reg_q;
  logic [31:0] wdata_next;

  assign wdata_next = {wdata_reg_q[30:0], mosi_sync};

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      cmd_reg_q            <= '0;
      wdata_reg_q           <= '0;
      data_nibble_count_q  <= NIBBLE_COUNT_DEFAULT;
      pause_pulse_enable_q <= 1'b0;
      crc_check_enable_q   <= 1'b1;
    end else if (cs_active && sck_rising) begin
      if (bit_cnt_q < 6'd8) begin
        cmd_reg_q <= {cmd_reg_q[6:0], mosi_sync};
      end else begin
        wdata_reg_q <= wdata_next;
        if (bit_cnt_q == 6'd39 && cmd_reg_q[7] && cmd_reg_q[6:0] == ADDR_CONFIG) begin
          pause_pulse_enable_q <= wdata_next[3];
          crc_check_enable_q   <= wdata_next[4];
          if (wdata_next[2:0] != 3'd0 && wdata_next[2:0] != 3'd7) begin
            data_nibble_count_q <= wdata_next[2:0];
          end
        end
      end
    end
  end

  logic [2:0] data_nibble_count_q;
  logic       pause_pulse_enable_q;
  logic       crc_check_enable_q;
  assign data_nibble_count  = data_nibble_count_q;
  assign pause_pulse_enable = pause_pulse_enable_q;
  assign crc_check_enable   = crc_check_enable_q;

  // ------------------------------------------------------------------
  // MISO shift register (MSB first), loaded once the address is known
  // ------------------------------------------------------------------
  logic [31:0] read_value;
  always_comb begin
    case (cmd_reg_q[6:0])
      ADDR_CONFIG:
      read_value = {27'b0, crc_check_enable_q, pause_pulse_enable_q, data_nibble_count_q};
      ADDR_STATUS: read_value = {30'b0, data_error, data_valid};
      ADDR_FRAME_DATA: read_value = frame_data;
      default: read_value = frame_data;  // unassigned addresses also read as frame_data
    endcase
  end

  logic [31:0] shift_reg;
  assign miso = shift_reg[31];

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      shift_reg <= '0;
    end else if (!cs_active) begin
      shift_reg <= '0;
    end else if (sck_falling) begin
      if (bit_cnt_q == 6'd8) begin
        shift_reg <= read_value;
      end else if (bit_cnt_q > 6'd8) begin
        shift_reg <= {shift_reg[30:0], 1'b0};
      end
    end
  end

endmodule
