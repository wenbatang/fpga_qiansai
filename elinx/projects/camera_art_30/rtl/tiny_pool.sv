// Even frame/strip width and origin. One 2x2 RGB mean, floor((sum+2)/4).
module tiny_pool #(parameter WIDTH=192,HEIGHT=720)(input wire clk,reset,start,
 input wire[23:0]in_rgb,input wire in_valid,output wire in_ready,
 output reg[23:0]out_rgb,output reg out_valid,input wire out_ready);
 localparam AB=$clog2(WIDTH/2);reg[15:0]x,y;reg[23:0]first;
 reg[26:0]pair_sum[0:WIDTH/2-1];reg[26:0]upper;
 wire step=!out_valid || out_ready;assign in_ready=step;
 wire[9:0]sr={2'b0,in_rgb[7:0]}+{2'b0,first[7:0]}+{1'b0,upper[8:0]}+10'd2;
 wire[9:0]sg={2'b0,in_rgb[15:8]}+{2'b0,first[15:8]}+{1'b0,upper[17:9]}+10'd2;
 wire[9:0]sb={2'b0,in_rgb[23:16]}+{2'b0,first[23:16]}+{1'b0,upper[26:18]}+10'd2;
 always @(posedge clk)begin
  if(out_valid && out_ready)out_valid<=0;
  if(in_valid && in_ready)begin
   if(!x[0])begin first<=in_rgb;upper<=pair_sum[x>>1];end
   else if(!y[0])pair_sum[x>>1]<={{1'b0,in_rgb[23:16]}+{1'b0,first[23:16]},{1'b0,in_rgb[15:8]}+{1'b0,first[15:8]},{1'b0,in_rgb[7:0]}+{1'b0,first[7:0]}};
   else begin out_rgb<={sb[9:2],sg[9:2],sr[9:2]};out_valid<=1;end
   if(x==WIDTH-1)begin x<=0;y<=y+1;end else x<=x+1;
  end
  if(reset || start)begin x<=0;y<=0;out_valid<=0;first<=0;upper<=0;end
 end
endmodule
