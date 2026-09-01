/*
 * Copyright (c) 2026 Philipp Kraft
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module sent2spi (
    input logic clk,
    input logic rst_n,

    input logic sent_in,

    input  logic cs,
    input  logic mosi,
    output logic miso,
    input  logic sck
);

  logic [31:0] frame_data;
  logic        frame_valid;
  logic        frame_error;

  sent_receiver i_sent_receiver (
      .clk(clk),
      .rst_n(rst_n),
      .sent_in(sent_in),
      .frame_data(frame_data),
      .frame_valid(frame_valid),
      .frame_error(frame_error)
  );

  spi_slave i_spi_slave (
      .clk(clk),
      .rst_n(rst_n),
      .frame_data(frame_data),
      .frame_valid(frame_valid),
      .frame_error(frame_error),
      .cs(cs),
      .mosi(mosi),
      .miso(miso),
      .sck(sck)
  );

endmodule
