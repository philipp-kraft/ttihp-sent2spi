/*
 * Copyright (c) 2026 Philipp Kraft
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module sent_receiver (
    input logic clk,
    input logic rst_n,

    input logic sent_in,

    output logic [31:0] frame_data,
    output logic        frame_valid,
    output logic        frame_error
);

  // ------------------------------------------------------------------
  // SENT input synchronizer
  // ------------------------------------------------------------------
  logic sent_in_sync;

  sync2ff i_sync2ff (
      .clk(clk),
      .rst_n(rst_n),
      .d(sent_in),
      .q(sent_in_sync)
  );

  // -------------------------------------------------------------------------
  // Edge detection
  // -------------------------------------------------------------------------
  logic sent_in_sync_prev;
  logic sent_falling;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      sent_in_sync_prev <= 1'b0;
    end else begin
      sent_in_sync_prev <= sent_in_sync;
    end
  end

  assign sent_falling = !sent_in_sync & sent_in_sync_prev;

  // -------------------------------------------------------------------------
  // Pulse Timing
  // -------------------------------------------------------------------------
  logic [15:0] tick_counter_d, tick_counter_q;

  always_comb begin
    tick_counter_d = sent_falling ? 16'd1 : tick_counter_q + 1'b1;
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      tick_counter_q <= '0;
    end else begin
      tick_counter_q <= tick_counter_d;
    end
  end

  // -------------------------------------------------------------------------
  // FSM
  // -------------------------------------------------------------------------
  typedef enum logic [1:0] {
    ST_SYNC,
    ST_NIBBLE,
    ST_CRC
  } sent_state_t;

  sent_state_t state_d, state_q;

  logic [15:0] tick_len_d, tick_len_q; // length of a SENT tick in cycles

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      tick_len_q <= '0;
    end else begin
      tick_len_q <= tick_len_d;
    end
  end

  always_comb begin
    case (state_q)
      ST_SYNC: begin
        tick_len_d = tick_len_q;

        if (sent_falling) begin
          tick_len_d = (tick_counter_q) / 56;
          state_d = ST_NIBBLE;
        end
      end
      ST_NIBBLE: state_d = ST_SYNC;
      ST_CRC: state_d = ST_SYNC;
      default: state_d = ST_SYNC;
    endcase
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state_q <= ST_SYNC;
    end else begin
      state_q <= state_d;
    end
  end

  assign frame_data = '0;
  assign frame_valid = '0;
  assign frame_error = '0;

endmodule
