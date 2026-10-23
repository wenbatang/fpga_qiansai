// Independent six-style Xilinx CNN: RGB -> 12 -> 12 -> 12 -> 12 -> RGB.
// Dilation 1/2/4/8/16; receptive field 63; 504 channel multipliers.
// Optional phase inputs use exact shift/add products without extra DSPs.
module style_cnn_stream5 #(
    parameter integer WIDTH=1280,HEIGHT=720,COORD_PHASE=0,
    parameter W0="",B0="",S0="",W1="",B1="",S1="",W2="",B2="",S2="",
    parameter W3="",B3="",S3="",W4="",B4="",S4=""
)(input wire clk,reset,start,input wire [2:0]style,
  input wire [23:0]in_rgb,input wire in_valid,output wire in_ready,
  output wire [23:0]out_rgb,output wire out_valid,input wire out_ready,output wire done);
    wire [95:0]a,b,c,d;
    wire av,ar,bv,br,cv,cr,dv,dr;
    localparam integer INPUT_CHANNELS=COORD_PHASE==4 ? 5:3;
    wire [INPUT_CHANNELS*8-1:0] input_features;
    generate if(COORD_PHASE==4)begin:g_coordinates
        reg[15:0]x,y;
        always @(posedge clk)begin
            if(reset || start)begin x<=0;y<=0;end
            else if(in_valid && in_ready)begin
                if(x==WIDTH-1)begin x<=0;y<=y+1;end else x<=x+1;
            end
        end
        assign input_features={{4{y[1:0]}},{4{x[1:0]}},in_rgb};
    end else begin:g_rgb
        assign input_features=in_rgb;
    end endgenerate
    style_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CIN(INPUT_CHANNELS),.COUT(12),.DILATION(1),.PHASE_INPUT(COORD_PHASE==4),.WEIGHT_FILE(W0),.BIAS_FILE(B0),.SHIFT_FILE(S0)) l0(
        .clk(clk),.reset(reset),.start(start),.style(style),.in_data(input_features),.in_valid(in_valid),.in_ready(in_ready),.out_data(a),.out_valid(av),.out_ready(ar),.done());
    style_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CIN(12),.COUT(12),.DILATION(2),.WEIGHT_FILE(W1),.BIAS_FILE(B1),.SHIFT_FILE(S1)) l1(
        .clk(clk),.reset(reset),.start(start),.style(style),.in_data(a),.in_valid(av),.in_ready(ar),.out_data(b),.out_valid(bv),.out_ready(br),.done());
    style_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CIN(12),.COUT(12),.DILATION(4),.WEIGHT_FILE(W2),.BIAS_FILE(B2),.SHIFT_FILE(S2)) l2(
        .clk(clk),.reset(reset),.start(start),.style(style),.in_data(b),.in_valid(bv),.in_ready(br),.out_data(c),.out_valid(cv),.out_ready(cr),.done());
    style_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CIN(12),.COUT(12),.DILATION(8),.WEIGHT_FILE(W3),.BIAS_FILE(B3),.SHIFT_FILE(S3)) l3(
        .clk(clk),.reset(reset),.start(start),.style(style),.in_data(c),.in_valid(cv),.in_ready(cr),.out_data(d),.out_valid(dv),.out_ready(dr),.done());
    style_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CIN(12),.COUT(3),.DILATION(16),.WEIGHT_FILE(W4),.BIAS_FILE(B4),.SHIFT_FILE(S4)) l4(
        .clk(clk),.reset(reset),.start(start),.style(style),.in_data(d),.in_valid(dv),.in_ready(dr),.out_data(out_rgb),.out_valid(out_valid),.out_ready(out_ready),.done(done));
endmodule
