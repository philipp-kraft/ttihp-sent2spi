`default_nettype none
`timescale 1ns / 1ps

/* Chip-level testbench for tt_um_sent2spi. Unlike tb_sent_receiver.v/tb_spi_slave.v
   (which instantiate the internal submodules directly for RTL unit testing), this
   wraps the top-level pin interface so it also works against the flattened
   gate-level netlist produced by hardening, which only exposes tt_um_sent2spi.
   Driven by test.py.
*/
module tb ();

  initial begin
    $dumpfile("tb.fst");
    $dumpvars(0, tb);
    #1;
  end

  reg clk;
  reg rst_n;
  reg ena;
  reg [7:0] ui_in;
  reg [7:0] uio_in;
  wire [7:0] uo_out;
  wire [7:0] uio_out;
  wire [7:0] uio_oe;

  tt_um_sent2spi user_project (
      .ui_in  (ui_in),
      .uo_out (uo_out),
      .uio_in (uio_in),
      .uio_out(uio_out),
      .uio_oe (uio_oe),
      .ena    (ena),
      .clk    (clk),
      .rst_n  (rst_n)
  );

endmodule
