/*
 * Copyright (c) 2026 Philipp Kraft
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_sent2spi (
    input  logic [7:0] ui_in,  // Dedicated inputs
    output logic [7:0] uo_out, // Dedicated outputs

    input  logic [7:0] uio_in,   // Bidirectional IO input path
    output logic [7:0] uio_out,  // Bidirectional IO output path
    output logic [7:0] uio_oe,   // 0 = input, 1 = output

    input logic ena,
    input logic clk,
    input logic rst_n
);

  localparam bit [7:0] UIO_OE = 8'b00000100;
  logic miso;

  assign uio_out = {5'b0, miso, 2'b0};
  assign uio_oe  = UIO_OE;

  sent2spi i_sent2spi (
      .clk(clk),
      .rst_n(rst_n),
      .sent_in(ui_in[0]),
      .cs(uio_in[0]),
      .mosi(uio_in[1]),
      .miso(miso),
      .sck(uio_in[3])
  );

endmodule
