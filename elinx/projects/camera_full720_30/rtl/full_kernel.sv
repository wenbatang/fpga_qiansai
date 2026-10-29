// One learned delta per full-resolution pixel. No pooling/resize/2x2 broadcast.
module full_kernel #(parameter WIDTH=352,HEIGHT=720,FRAME_WIDTH=1280,CHANNELS=6)(
 input wire clk,reset,start,input wire signed[15:0]origin_x,
 input wire[23:0]in_rgb,input wire in_valid,output wire in_ready,
 output wire[23:0]out_rgb,output wire out_valid,input wire out_ready,output reg done,
 input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);
 localparam RAW_DEPTH=1<<$clog2(WIDTH*20),AB=$clog2(RAW_DEPTH);
 (* ram_style="block" *)reg[23:0]raw_memory[0:RAW_DEPTH-1];
 reg[AB-1:0]wp,rp;reg[AB:0]count;reg[23:0]raw_word;reg raw_valid,running;
 reg[31:0]input_count,output_count;reg[15:0]input_x;reg signed[15:0]origin;
 wire signed[16:0]global_x=$signed(origin)+$signed({1'b0,input_x});
 wire input_inside=global_x>=0 && global_x<FRAME_WIDTH;
 wire[CHANNELS*8-1:0]f[0:4];wire[4:0]fv,fr,fi;wire stem_ready;
 assign in_ready=running && input_count<WIDTH*HEIGHT && count<RAW_DEPTH && stem_ready;
 wire push=in_valid && in_ready;
 full_pointwise #(.CIN(3),.COUT(CHANNELS),.LAYER(0),.RESIDUAL(0)) stem(
 .clk(clk),.reset(reset || start),.in_data(in_rgb),.in_skip({CHANNELS*8{1'b0}}),.in_inside(input_inside),
 .in_valid(in_valid && running && input_count<WIDTH*HEIGHT && count<RAW_DEPTH),.in_ready(stem_ready),
 .out_data(f[0]),.out_valid(fv[0]),.out_ready(fr[0]),.out_inside(fi[0]),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));
 genvar b;
 generate for(b=0;b<4;b=b+1)begin:block
  wire[CHANNELS*8-1:0]dw,skip;wire dv,dr,inside_pixel;
  full_dw3x3 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.FRAME_WIDTH(FRAME_WIDTH),.CHANNELS(CHANNELS),.DILATION(1<<b),.LAYER(1+2*b)) spatial(
   .clk(clk),.reset(reset),.start(start),.origin_x(origin_x),.in_data(f[b]),.in_valid(fv[b]),.in_ready(fr[b]),
   .out_data(dw),.out_center(skip),.out_inside(inside_pixel),.out_valid(dv),.out_ready(dr),
   .cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));
  full_pointwise #(.CIN(CHANNELS),.COUT(CHANNELS),.LAYER(2+2*b)) mixing(
   .clk(clk),.reset(reset || start),.in_data(dw),.in_skip(skip),.in_inside(inside_pixel),.in_valid(dv),.in_ready(dr),
   .out_data(f[b+1]),.out_valid(fv[b+1]),.out_ready(fr[b+1]),.out_inside(fi[b+1]),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));
 end endgenerate
 wire[47:0]delta;wire delta_valid,delta_ready;
 full_pointwise #(.CIN(CHANNELS),.COUT(3),.LAYER(9),.HEAD(1),.RESIDUAL(0)) head(
  .clk(clk),.reset(reset || start),.in_data(f[4]),.in_skip(24'd0),.in_inside(fi[4]),.in_valid(fv[4]),.in_ready(fr[4]),
  .out_data(delta),.out_valid(delta_valid),.out_ready(delta_ready),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));
 assign out_valid=running && raw_valid && delta_valid;
 assign delta_ready=running && raw_valid && out_ready;
 wire take=out_valid && out_ready;
 wire prefetch=(!raw_valid || take) && count!=0;
 wire signed[16:0]red=$signed({1'b0,raw_word[7:0]})+$signed(delta[15:0]);
 wire signed[16:0]green=$signed({1'b0,raw_word[15:8]})+$signed(delta[31:16]);
 wire signed[16:0]blue=$signed({1'b0,raw_word[23:16]})+$signed(delta[47:32]);
 function automatic[7:0]clip(input signed[16:0]v);begin clip=v<0?0:v>255?255:v[7:0];end endfunction
 assign out_rgb={clip(blue),clip(green),clip(red)};
 always @(posedge clk)begin
  done<=0;
  if(push)begin raw_memory[wp]<=in_rgb;wp<=wp+1'b1;input_count<=input_count+1;input_x<=input_x==WIDTH-1?0:input_x+1'b1;end
  if(prefetch)begin raw_word<=raw_memory[rp];rp<=rp+1'b1;raw_valid<=1;end
  else if(take)raw_valid<=0;
  case({push,prefetch})2'b10:count<=count+1'b1;2'b01:count<=count-1'b1;default:begin end endcase
  if(take)begin output_count<=output_count+1;if(output_count==WIDTH*HEIGHT-1)begin running<=0;done<=1;end end
  if(reset || start)begin running<=!reset;wp<=0;rp<=0;count<=0;raw_valid<=0;input_count<=0;output_count<=0;input_x<=0;origin<=origin_x;end
 end
endmodule
