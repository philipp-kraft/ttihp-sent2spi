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
    input  logic sck,

    output logic data_valid,
    output logic data_error
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
      .cs(cs),
      .mosi(mosi),
      .miso(miso),
      .sck(sck)
  );

  // latches the one-cycle frame_valid/frame_error pulses so uo_out can be polled
  logic data_valid_d, data_valid_q;
  logic data_error_d, data_error_q;

  always_comb begin
    data_valid_d = data_valid_q;
    data_error_d = data_error_q;
    if (frame_valid) begin
      data_valid_d = 1'b1;
      data_error_d = 1'b0;
    end else if (frame_error) begin
      data_error_d = 1'b1;
    end
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      data_valid_q <= 1'b0;
      data_error_q <= 1'b0;
    end else begin
      data_valid_q <= data_valid_d;
      data_error_q <= data_error_d;
    end
  end

  assign data_valid = data_valid_q;
  assign data_error = data_error_q;

endmodule
