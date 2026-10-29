// Complete even-sized RGB strip -> exact TinyStyle47 C8 output. Half-size
// computation, full-size original RGB bypass; all spatial phases are global.
module tiny_kernel #(parameter WIDTH=192,HEIGHT=720,FRAME_WIDTH=1280)(
 input wire clk,reset,start,input wire signed[15:0]origin_x,
 input wire[23:0]in_rgb,input wire in_valid,output wire in_ready,
 output reg[23:0]out_rgb,output reg out_valid,input wire out_ready,output reg done,
 input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);
 localparam LW=WIDTH/2,LH=HEIGHT/2;
 localparam RAW_DEPTH=1<<$clog2(WIDTH*40),RAW_AB=$clog2(RAW_DEPTH);
 wire[23:0]pooled;wire pv,pr,pool_ready;
 reg running;reg[31:0]input_count,emitted,accepted;
 reg[RAW_AB-1:0]wp,rp;reg[RAW_AB:0]count;
 (* ram_style="block" *)reg[23:0]raw_memory[0:RAW_DEPTH-1];
 reg[23:0]raw_word;reg raw_valid;
 wire can_emit=!out_valid || out_ready;
 wire consume_raw;
 wire prefetch=(!raw_valid || consume_raw) && count!=0;
 wire push=in_valid && in_ready;
 assign in_ready=running && input_count<WIDTH*HEIGHT && count<RAW_DEPTH && pr;
 tiny_pool #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) pooling(.clk(clk),.reset(reset),.start(start),
 .in_rgb(in_rgb),.in_valid(in_valid && running && count<RAW_DEPTH && input_count<WIDTH*HEIGHT),.in_ready(pr),.out_rgb(pooled),.out_valid(pv),.out_ready(pool_ready));
 wire[63:0]f[0:4];wire[4:0]fv,fr;
 tiny_spatial #(.WIDTH(LW),.HEIGHT(LH),.FRAME_WIDTH(FRAME_WIDTH/2),.CIN(3),.COUT(8),.DW(0),.LAYER(0)) stem(
 .clk(clk),.reset(reset),.start(start),.origin_x(origin_x>>>1),.in_data(pooled),.in_valid(pv),.in_ready(pool_ready),.out_data(f[0]),.out_center(),.out_inside(),.out_valid(fv[0]),.out_ready(fr[0]),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));
 genvar b;
 generate for(b=0;b<4;b=b+1)begin:block
  wire[63:0]dw,skip;wire dv,dr,inside_pixel;
  tiny_spatial #(.WIDTH(LW),.HEIGHT(LH),.FRAME_WIDTH(FRAME_WIDTH/2),.CIN(8),.COUT(8),.DILATION(1<<b),.DW(1),.LAYER(1+2*b)) spatial(
  .clk(clk),.reset(reset),.start(start),.origin_x(origin_x>>>1),.in_data(f[b]),.in_valid(fv[b]),.in_ready(fr[b]),.out_data(dw),.out_center(skip),.out_inside(inside_pixel),.out_valid(dv),.out_ready(dr),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));
  tiny_pointwise #(.LAYER(2+2*b)) mixing(.clk(clk),.reset(reset),.in_data(dw),.in_skip(skip),.in_inside(inside_pixel),.in_valid(dv),.in_ready(dr),.out_data(f[b+1]),.out_valid(fv[b+1]),.out_ready(fr[b+1]),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));
 end endgenerate
 wire[47:0]delta;wire delta_valid,delta_ready;
 tiny_pointwise #(.COUT(3),.LAYER(9),.HEAD(1)) head(.clk(clk),.reset(reset),.in_data(f[4]),.in_skip(64'd0),.in_inside(1'b1),.in_valid(fv[4]),.in_ready(fr[4]),.out_data(delta),.out_valid(delta_valid),.out_ready(delta_ready),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));
 reg[15:0]ox,oy;
 (* ram_style="block" *)reg[47:0]delta_line[0:LW-1];reg[47:0]delta_hold,line_word;reg line_valid;
 wire first_pair=!oy[0] && !ox[0];
 wire available=oy[0] ? (ox[0] || line_valid):(ox[0] || delta_valid);
 wire emit_pixel=running && emitted<WIDTH*HEIGHT && can_emit && raw_valid && available;
 assign consume_raw=emit_pixel;
 assign delta_ready=emit_pixel && first_pair;
 wire[47:0]selected=first_pair?delta:oy[0] && !ox[0]?line_word:delta_hold;
 wire signed[16:0]red=$signed({1'b0,raw_word[7:0]})+$signed(selected[15:0]);
 wire signed[16:0]green=$signed({1'b0,raw_word[15:8]})+$signed(selected[31:16]);
 wire signed[16:0]blue=$signed({1'b0,raw_word[23:16]})+$signed(selected[47:32]);
 function automatic[7:0]clip(input signed[16:0]v);begin clip=v<0?0:v>255?255:v[7:0];end endfunction
 always @(posedge clk)begin
  done<=0;
  if(push)begin raw_memory[wp]<=in_rgb;wp<=wp+1'b1;input_count<=input_count+1;end
  if(prefetch)begin raw_word<=raw_memory[rp];rp<=rp+1'b1;raw_valid<=1;end
  else if(consume_raw)raw_valid<=0;
  case({push,prefetch})2'b10:count<=count+1;2'b01:count<=count-1;default:begin end endcase
  if(can_emit)begin
   if(out_valid && out_ready)out_valid<=0;
   if(emit_pixel)begin
    out_valid<=1;out_rgb<={clip(blue),clip(green),clip(red)};emitted<=emitted+1;
    if(!ox[0])delta_hold<=selected;
    if(first_pair)delta_line[ox>>1]<=delta;
    if(oy[0] && ox[0])line_valid<=0;
    if(ox==WIDTH-1)begin ox<=0;oy<=oy+1;end else ox<=ox+1;
   end
  end
  if(running && oy[0] && !ox[0] && !line_valid && can_emit)begin line_word<=delta_line[ox>>1];line_valid<=1;end
  if(out_valid && out_ready)begin accepted<=accepted+1;if(accepted==WIDTH*HEIGHT-1)begin running<=0;done<=1;end end
  if(reset || start)begin running<=!reset;input_count<=0;wp<=0;rp<=0;count<=0;raw_valid<=0;out_valid<=0;ox<=0;oy<=0;line_valid<=0;emitted<=0;accepted<=0;delta_hold<=0;line_word<=0;end
 end
endmodule
