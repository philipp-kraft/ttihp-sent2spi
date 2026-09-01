/*
 * Copyright (c) 2026 Philipp Kraft
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module spi_slave (
    input logic clk,
    input logic rst_n,

    input logic [31:0] frame_data,
    input logic        frame_valid,
    input logic        frame_error,

    input  logic cs,
    input  logic mosi,
    output logic miso,
    input  logic sck
);

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

  // ------------------------------------------------------------------
  // Shift register (MSB first)
  // ------------------------------------------------------------------
  logic cs_active;
  logic [31:0] shift_reg;

  assign cs_active = !cs_sync;
  assign miso = shift_reg[31];

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      shift_reg <= '0;
    end else if (!cs_active) begin
      shift_reg <= frame_data;
    end else if (sck_falling) begin
      shift_reg <= {shift_reg[30:0], 1'b0};
    end
  end

endmodule
