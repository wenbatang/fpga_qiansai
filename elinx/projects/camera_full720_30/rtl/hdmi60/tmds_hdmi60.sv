// HDMI transmitter from the board's unchanged demo10 V7, used through its
// public ports under the vendor tool license. No protected source is modified.
// CTA VIC 4 = 1280x720p60, RGB 4:4:4, 74.25 MHz, no pixel repetition.
module tmds_hdmi60(input wire clk,reset,input wire [23:0] rgb,
 input wire de,hsync,vsync,
 output wire [9:0] blue,green,red,clock_word);
 wire [9:0] b,g,r,c;
 dvi_encoder transmitter(.pixelclk(clk),.rst_p(reset),
  .i_bdata(rgb[7:0]),.i_gdata(rgb[15:8]),.i_rdata(rgb[23:16]),
  .i_hs(hsync),.i_vs(vsync),.i_de(de),
  .video_format(2'b00),.video_VIC(7'd4),
  .audio_L(24'd0),.audio_R(24'd0),.audio_valid(1'b0),
  .audio_N(20'd6144),.audio_CTS(20'd74250),
  .audio_sample_frequency(4'b0010),.audio_word_length(4'b1011),
  .tmds_data0(b),.tmds_data1(g),.tmds_data2(r),.tmds_clk(c));
 // The V4 PCB swaps P/N between FPGA and HDMI socket on all four pairs.
 assign blue=~b;assign green=~g;assign red=~r;assign clock_word=~c;
endmodule
