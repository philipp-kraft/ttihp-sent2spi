`default_nettype none
`timescale 1ns / 1ps

/* Unit testbench for sent_receiver, bypassing the tt_um_sent2spi top level
   (which doesn't instantiate it yet). Driven by test_sent_receiver.py.
*/
module tb_sent_receiver ();

  initial begin
    $dumpfile("tb_sent_receiver.fst");
    $dumpvars(0, tb_sent_receiver);
    #1;
  end

  reg clk;
  reg rst_n;
  reg sent_in;

  wire [31:0] frame_data;
  wire frame_valid;
  wire frame_error;

  sent_receiver i_sent_receiver (
      .clk        (clk),
      .rst_n      (rst_n),
      .sent_in    (sent_in),
      .frame_data (frame_data),
      .frame_valid(frame_valid),
      .frame_error(frame_error)
  );

endmodule
