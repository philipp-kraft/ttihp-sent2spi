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
    ST_IDLE,
    ST_SYNC,
    ST_NIBBLE,
    ST_CRC
  } sent_state_t;

  sent_state_t state_d, state_q;

  localparam int NUM_NIBBLES = 8;  // 1 status nibble + 6 data nibbles +1 crc nibble

  logic [15:0] tick_len_d, tick_len_q;  // length of a SENT tick in cycles
  logic [2:0] nibble_id_d, nibble_id_q;  // which nibble we are on
  logic [31:0] frame_shift_d, frame_shift_q;  // data, shifted in nibble by nibble
  logic [31:0] frame_data_d, frame_data_q;  // last valid frame, held until overwritten
  logic frame_valid_d, frame_valid_q;  // one-cycle pulse
  logic frame_error_d, frame_error_q;  // one-cycle pulse
  logic [3:0] nibble;  // decoded value of pulse

  assign frame_data  = frame_data_q;
  assign frame_valid = frame_valid_q;
  assign frame_error = frame_error_q;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state_q       <= ST_IDLE;
      tick_len_q    <= '0;
      nibble_id_q   <= '0;
      frame_shift_q <= '0;
      frame_data_q  <= '0;
      frame_valid_q <= '0;
      frame_error_q <= '0;
    end else begin
      tick_len_q    <= tick_len_d;
      nibble_id_q   <= nibble_id_d;
      frame_shift_q <= frame_shift_d;
      frame_data_q  <= frame_data_d;
      frame_valid_q <= frame_valid_d;
      frame_error_q <= frame_error_d;
      state_q       <= state_d;
    end
  end

  always_comb begin
    state_d       = state_q;
    tick_len_d    = tick_len_q;
    nibble_id_d   = nibble_id_q;
    frame_shift_d = frame_shift_q;
    frame_data_d  = frame_data_q;
    frame_valid_d = 1'b0;
    frame_error_d = 1'b0;
    nibble        = '0;

    case (state_q)
      ST_IDLE: begin
        if (sent_falling) begin
          state_d = ST_SYNC;
        end
      end
      ST_SYNC: begin
        if (sent_falling) begin
          tick_len_d    = tick_counter_q / 56;
          nibble_id_d   = '0;
          frame_shift_d = '0;
          state_d       = ST_NIBBLE;
        end
      end
      ST_NIBBLE: begin
        if (sent_falling) begin
          nibble = tick_counter_q / tick_len_q - 16'd12;
          frame_shift_d = {frame_shift_q[27:0], nibble};

          if (nibble_id_q == NUM_NIBBLES - 1) begin
            state_d = ST_CRC;
          end else begin
            nibble_id_d = nibble_id_q + 1'b1;
          end
        end
      end
      ST_CRC: begin
        if (frame_shift_q[3:0] == 4'b0000) begin
          state_d       = ST_SYNC;
          frame_valid_d = 1'b1;
          frame_data_d  = frame_shift_q;
        end else begin
          frame_error_d = 1'b1;
        end
      end
      default: state_d = ST_SYNC;
    endcase
  end

endmodule
