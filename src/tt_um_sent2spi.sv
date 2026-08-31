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

  // we never use the bidirectional io as output
  assign uio_out = 0;
  assign uio_oe  = 0;

endmodule
