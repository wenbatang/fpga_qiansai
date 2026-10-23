// Portable stream accelerator. File paths are generated from real learned
// weights by the project preparation tool; no random/fallback weights.
module style_cnn_stream #(
    parameter integer WIDTH=1280, HEIGHT=720,
    parameter W0="", B0="", S0="", W1="", B1="", S1="", W2="", B2="", S2=""
)(input wire clk,reset,start,input wire [2:0] style,
  input wire [23:0] in_rgb,input wire in_valid,output wire in_ready,
  output wire [23:0] out_rgb,output wire out_valid,input wire out_ready,
  output wire done);
    wire [63:0] a,b;
    wire av,ar,bv,br;
    style_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CIN(3),.COUT(8),.DILATION(1),
        .WEIGHT_FILE(W0),.BIAS_FILE(B0),.SHIFT_FILE(S0)) first(
        .clk(clk),.reset(reset),.start(start),.style(style),.in_data(in_rgb),.in_valid(in_valid),.in_ready(in_ready),
        .out_data(a),.out_valid(av),.out_ready(ar),.done());
    style_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CIN(8),.COUT(8),.DILATION(2),
        .WEIGHT_FILE(W1),.BIAS_FILE(B1),.SHIFT_FILE(S1)) middle(
        .clk(clk),.reset(reset),.start(start),.style(style),.in_data(a),.in_valid(av),.in_ready(ar),
        .out_data(b),.out_valid(bv),.out_ready(br),.done());
    style_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CIN(8),.COUT(3),.DILATION(4),
        .WEIGHT_FILE(W2),.BIAS_FILE(B2),.SHIFT_FILE(S2)) last(
        .clk(clk),.reset(reset),.start(start),.style(style),.in_data(b),.in_valid(bv),.in_ready(br),
        .out_data(out_rgb),.out_valid(out_valid),.out_ready(out_ready),.done(done));
endmodule
