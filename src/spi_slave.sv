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


endmodule
