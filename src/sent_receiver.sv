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
  // tick_counter_q is a raw clock-cycle counter, reset on every falling edge.
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

  // Per-nibble pulse length, measured directly in SENT ticks instead of
  // dividing tick_counter_q by the runtime-variable tick_len_q.
  logic [15:0] subtick_d, subtick_q;
  logic [15:0] tick_cnt_d, tick_cnt_q;

  always_comb begin
    if (sent_falling) begin
      subtick_d = 16'd1;
    end else if (subtick_q == tick_len_q) begin
      subtick_d = 16'd1;
    end else begin
      subtick_d = subtick_q + 1'b1;
    end
  end

  always_comb begin
    if (sent_falling) begin
      tick_cnt_d = '0;
    end else if (subtick_q == tick_len_q - 1'b1) begin
      tick_cnt_d = tick_cnt_q + 1'b1;
    end else begin
      tick_cnt_d = tick_cnt_q;
    end
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      subtick_q  <= '0;
      tick_cnt_q <= '0;
    end else begin
      subtick_q  <= subtick_d;
      tick_cnt_q <= tick_cnt_d;
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

  // SAE J2716 CRC-4: seed 5, poly x^4+x^3+x^2+1 (0x13), computed over the
  // status nibble and the 6 data nibbles, checked against the CRC nibble.
  localparam logic [3:0] CRC_SEED = 4'h5;
  localparam logic [4:0] CRC_POLY = 5'h13;

  function automatic logic [3:0] crc4_step(input logic [3:0] crc_in, input logic [3:0] nibble_in);
    logic [3:0] c;
    logic [4:0] shifted;
    begin
      c = crc_in ^ nibble_in;
      for (int k = 0; k < 4; k++) begin
        shifted = {1'b0, c} << 1;
        if (c[3]) shifted = shifted ^ CRC_POLY;
        c = shifted[3:0];
      end
      crc4_step = c;
    end
  endfunction

  logic [15:0] tick_len_d, tick_len_q;  // length of a SENT tick in cycles
  logic [2:0] nibble_id_d, nibble_id_q;  // which nibble we are on
  logic [31:0] frame_shift_d, frame_shift_q;  // data, shifted in nibble by nibble
  logic [31:0] frame_data_d, frame_data_q;  // last valid frame, held until overwritten
  logic frame_valid_d, frame_valid_q;  // one-cycle pulse
  logic frame_error_d, frame_error_q;  // one-cycle pulse
  logic [3:0] nibble;  // decoded value of pulse
  logic [3:0] crc_d, crc_q;  // running CRC over status + data nibbles

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
      crc_q         <= CRC_SEED;
    end else begin
      tick_len_q    <= tick_len_d;
      nibble_id_q   <= nibble_id_d;
      frame_shift_q <= frame_shift_d;
      frame_data_q  <= frame_data_d;
      frame_valid_q <= frame_valid_d;
      frame_error_q <= frame_error_d;
      state_q       <= state_d;
      crc_q         <= crc_d;
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
    crc_d         = crc_q;
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
          crc_d         = CRC_SEED;
          state_d       = ST_NIBBLE;
        end
      end
      ST_NIBBLE: begin
        if (sent_falling) begin
          nibble = tick_cnt_q - 16'd12;
          frame_shift_d = {frame_shift_q[27:0], nibble};

          if (nibble_id_q == NUM_NIBBLES - 1) begin
            // this nibble is the CRC nibble itself; it is not folded into the running CRC
            state_d = ST_CRC;
          end else begin
            crc_d       = crc4_step(crc_q, nibble);
            nibble_id_d = nibble_id_q + 1'b1;
          end
        end
      end
      ST_CRC: begin
        state_d = ST_SYNC;
        if (frame_shift_q[3:0] == crc_q) begin
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
