/*
 * Copyright (c) 2026 Philipp Kraft
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module sync2ff (
    input logic clk,
    input logic rst_n,

    input  logic d,
    output logic q
);

  logic q1;
  logic q2;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      q1 <= 1'b0;
      q2 <= 1'b0;
    end else begin
      q1 <= d;
      q2 <= q1;
    end
  end

  assign q = q2;

endmodule
