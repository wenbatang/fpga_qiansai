// V4 PCB connects FPGA N pads to connector TMDS P nets (and conversely).
// Invert all three canonical TMDS words and the clock, as the V7 example does.
module tmds_efx(input wire clk,reset,input wire [23:0] rgb,input wire de,hsync,vsync,
 output wire [9:0] blue,green,red,clock_word);
    wire [9:0] b,g,r;
    hdmi_encoder eb(.clkin(clk),.rstin(reset),.din(rgb[7:0]),.c0(hsync),.c1(vsync),.de(de),.dout(b));
    hdmi_encoder eg(.clkin(clk),.rstin(reset),.din(rgb[15:8]),.c0(1'b0),.c1(1'b0),.de(de),.dout(g));
    hdmi_encoder er(.clkin(clk),.rstin(reset),.din(rgb[23:16]),.c0(1'b0),.c1(1'b0),.de(de),.dout(r));
    assign blue=~b;assign green=~g;assign red=~r;
    assign clock_word=~10'b1111100000;
endmodule
