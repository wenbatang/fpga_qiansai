// Folded twelve-channel model; every layer uses full-image mirror boundaries.
module fps12_cnn5 #(
 parameter WIDTH=128,HEIGHT=720,FRAME_WIDTH=1280,STYLE_COUNT=1,
 parameter W0="",B0="",S0="",W1="",B1="",S1="",W2="",B2="",S2="",W3="",B3="",S3="",W4="",B4="",S4=""
)(input wire clk,reset,start,input wire[2:0]style,input wire signed[15:0]origin_x,
 input wire[23:0]in_rgb,input wire in_valid,output wire in_ready,
 output wire[23:0]out_rgb,output wire out_valid,input wire out_ready,output wire done,input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);
 wire[95:0]a,b,c,d;wire av,ar,bv,br,cv,cr,dv,dr;
 fps12_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.FRAME_WIDTH(FRAME_WIDTH),.CIN(3),.COUT(12),.DILATION(1),.STYLE_COUNT(STYLE_COUNT),.WEIGHT_FILE(W0),.BIAS_FILE(B0),.SHIFT_FILE(S0)) l0(
 .clk(clk),.reset(reset),.start(start),.style(style),.origin_x(origin_x),.in_data(in_rgb),.in_valid(in_valid),.in_ready(in_ready),.out_data(a),.out_valid(av),.out_ready(ar),.done(),.cfg_valid(cfg_valid && cfg_address[13:11]==3'd0),.cfg_address(cfg_address),.cfg_data(cfg_data));
 fps12_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.FRAME_WIDTH(FRAME_WIDTH),.CIN(12),.COUT(12),.DILATION(2),.STYLE_COUNT(STYLE_COUNT),.WEIGHT_FILE(W1),.BIAS_FILE(B1),.SHIFT_FILE(S1)) l1(
 .clk(clk),.reset(reset),.start(start),.style(style),.origin_x(origin_x),.in_data(a),.in_valid(av),.in_ready(ar),.out_data(b),.out_valid(bv),.out_ready(br),.done(),.cfg_valid(cfg_valid && cfg_address[13:11]==3'd1),.cfg_address(cfg_address),.cfg_data(cfg_data));
 fps12_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.FRAME_WIDTH(FRAME_WIDTH),.CIN(12),.COUT(12),.DILATION(4),.STYLE_COUNT(STYLE_COUNT),.WEIGHT_FILE(W2),.BIAS_FILE(B2),.SHIFT_FILE(S2)) l2(
 .clk(clk),.reset(reset),.start(start),.style(style),.origin_x(origin_x),.in_data(b),.in_valid(bv),.in_ready(br),.out_data(c),.out_valid(cv),.out_ready(cr),.done(),.cfg_valid(cfg_valid && cfg_address[13:11]==3'd2),.cfg_address(cfg_address),.cfg_data(cfg_data));
 fps12_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.FRAME_WIDTH(FRAME_WIDTH),.CIN(12),.COUT(12),.DILATION(8),.STYLE_COUNT(STYLE_COUNT),.WEIGHT_FILE(W3),.BIAS_FILE(B3),.SHIFT_FILE(S3)) l3(
 .clk(clk),.reset(reset),.start(start),.style(style),.origin_x(origin_x),.in_data(c),.in_valid(cv),.in_ready(cr),.out_data(d),.out_valid(dv),.out_ready(dr),.done(),.cfg_valid(cfg_valid && cfg_address[13:11]==3'd3),.cfg_address(cfg_address),.cfg_data(cfg_data));
 fps12_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.FRAME_WIDTH(FRAME_WIDTH),.CIN(12),.COUT(3),.DILATION(16),.STYLE_COUNT(STYLE_COUNT),.WEIGHT_FILE(W4),.BIAS_FILE(B4),.SHIFT_FILE(S4)) l4(
 .clk(clk),.reset(reset),.start(start),.style(style),.origin_x(origin_x),.in_data(d),.in_valid(dv),.in_ready(dr),.out_data(out_rgb),.out_valid(out_valid),.out_ready(out_ready),.done(done),.cfg_valid(cfg_valid && cfg_address[13:11]==3'd4),.cfg_address(cfg_address),.cfg_data(cfg_data));
endmodule
