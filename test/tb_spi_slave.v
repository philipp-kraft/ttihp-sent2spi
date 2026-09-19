`default_nettype none
`timescale 1ns / 1ps

/* Unit testbench for spi_slave, bypassing sent_receiver and the tt_um_sent2spi
   top level. Driven by test_spi_slave.py.
*/
module tb_spi_slave ();

  initial begin
    $dumpfile("tb_spi_slave.fst");
    $dumpvars(0, tb_spi_slave);
    #1;
  end

  reg clk;
  reg rst_n;

  reg [31:0] frame_data;

  reg cs;
  reg mosi;
  wire miso;
  reg sck;

  wire [2:0] data_nibble_count;

  spi_slave i_spi_slave (
      .clk              (clk),
      .rst_n            (rst_n),
      .frame_data       (frame_data),
      .cs               (cs),
      .mosi             (mosi),
      .miso             (miso),
      .sck              (sck),
      .data_nibble_count(data_nibble_count)
  );

endmodule
