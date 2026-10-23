// Exact five-layer inference on an overlapping vertical strip.
// Receptive radius = 1+1+2+4+8 = 16. Only the central strip is retained.
// Mask every layer outside the FULL image: input-only zero padding is wrong
// when biased hidden layers would create features outside the true boundary.
module style_tile_mask #(parameter WIDTH=352,FRAME_WIDTH=1280,CHANNELS=6)(
    input wire clk,reset,start,input wire signed [15:0] origin_x,
    input wire [CHANNELS*8-1:0] data,input wire valid,ready,
    output wire [CHANNELS*8-1:0] masked);
    reg [15:0] x;
    wire signed [16:0] global_x=$signed({origin_x[15],origin_x})+$signed({1'b0,x});
    assign masked=(global_x>=0 && global_x<FRAME_WIDTH) ? data : {CHANNELS*8{1'b0}};
    always @(posedge clk)begin
        if(reset || start)x<=0;
        else if(valid && ready)x<=x==WIDTH-1 ? 0:x+1;
    end
endmodule

module style_cnn_tile5 #(
    parameter WIDTH=352,HEIGHT=720,FRAME_WIDTH=1280,
    parameter W0="",B0="",S0="",W1="",B1="",S1="",W2="",B2="",S2="",
    parameter W3="",B3="",S3="",W4="",B4="",S4=""
)(input wire clk,reset,start,input wire[1:0] style,input wire signed [15:0] origin_x,
  input wire[23:0] in_rgb,input wire in_valid,output wire in_ready,
  output wire[23:0] out_rgb,output wire out_valid,input wire out_ready,output wire done);
    reg [15:0] x,y;
    reg signed [15:0] origin;
    wire signed [16:0] gx=$signed({origin[15],origin})+$signed({1'b0,x});
    wire [1:0] phase_x=x[1:0]+origin[1:0];
    wire [39:0] features=(gx>=0 && gx<FRAME_WIDTH) ? {{4{y[1:0]}},{4{phase_x}},in_rgb}:40'd0;
    always @(posedge clk)begin
        if(reset)begin x<=0;y<=0;origin<=0;end
        else if(start)begin x<=0;y<=0;origin<=origin_x;end
        else if(in_valid && in_ready)begin
            if(x==WIDTH-1)begin x<=0;y<=y+1;end else x<=x+1;
        end
    end
    wire[47:0] a,b,c,d,ma,mb,mc,md;wire[23:0] e;
    wire av,ar,bv,br,cv,cr,dv,dr;
    style_tile_mask #(.WIDTH(WIDTH),.FRAME_WIDTH(FRAME_WIDTH)) mask0(clk,reset,start,origin_x,a,av,ar,ma);
    style_tile_mask #(.WIDTH(WIDTH),.FRAME_WIDTH(FRAME_WIDTH)) mask1(clk,reset,start,origin_x,b,bv,br,mb);
    style_tile_mask #(.WIDTH(WIDTH),.FRAME_WIDTH(FRAME_WIDTH)) mask2(clk,reset,start,origin_x,c,cv,cr,mc);
    style_tile_mask #(.WIDTH(WIDTH),.FRAME_WIDTH(FRAME_WIDTH)) mask3(clk,reset,start,origin_x,d,dv,dr,md);
    style_tile_mask #(.WIDTH(WIDTH),.FRAME_WIDTH(FRAME_WIDTH),.CHANNELS(3)) mask4(clk,reset,start,origin_x,e,out_valid,out_ready,out_rgb);
    style_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CIN(5),.COUT(6),.DILATION(1),.PHASE_INPUT(1),.WEIGHT_FILE(W0),.BIAS_FILE(B0),.SHIFT_FILE(S0)) l0(
        clk,reset,start,style,features,in_valid,in_ready,a,av,ar,);
    style_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CIN(6),.COUT(6),.DILATION(1),.WEIGHT_FILE(W1),.BIAS_FILE(B1),.SHIFT_FILE(S1)) l1(
        clk,reset,start,style,ma,av,ar,b,bv,br,);
    style_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CIN(6),.COUT(6),.DILATION(2),.WEIGHT_FILE(W2),.BIAS_FILE(B2),.SHIFT_FILE(S2)) l2(
        clk,reset,start,style,mb,bv,br,c,cv,cr,);
    style_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CIN(6),.COUT(6),.DILATION(4),.WEIGHT_FILE(W3),.BIAS_FILE(B3),.SHIFT_FILE(S3)) l3(
        clk,reset,start,style,mc,cv,cr,d,dv,dr,);
    style_conv3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.CIN(6),.COUT(3),.DILATION(8),.WEIGHT_FILE(W4),.BIAS_FILE(B4),.SHIFT_FILE(S4)) l4(
        clk,reset,start,style,md,dv,dr,e,out_valid,out_ready,done);
endmodule
