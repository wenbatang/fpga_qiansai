// Raw preview copies a locked source through the SAME output write/commit
// path. Weights still load into the real CNN; raw is not neural inference.
module video_cnn_view_pipe #(
 parameter integer WIDTH=96,HEIGHT=480,FRAME_WIDTH=640,
 parameter W0="",B0="",S0="",W1="",B1="",S1="",W2="",B2="",S2="",
 parameter W3="",B3="",S3="",W4="",B4="",S4=""
)(input wire clk,reset,start,raw_mode,input wire[2:0] style,input wire signed[15:0] origin_x,
 input wire[23:0] in_rgb,input wire in_valid,output wire in_ready,
 output wire[23:0] out_rgb,output wire out_valid,input wire out_ready,output wire done,
 input wire cfg_valid,input wire[15:0] cfg_address,input wire[31:0] cfg_data);
 wire ci_ready,co_valid,cdone;wire[23:0] co_rgb;
 reg raw_running,raw_done;reg[31:0] raw_count;
 video_cnn_tile5_pipe #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.FRAME_WIDTH(FRAME_WIDTH),
  .W0(W0),.B0(B0),.S0(S0),.W1(W1),.B1(B1),.S1(S1),.W2(W2),.B2(B2),.S2(S2),
  .W3(W3),.B3(B3),.S3(S3),.W4(W4),.B4(B4),.S4(S4)) neural(
  .clk(clk),.reset(reset),.start(start && !raw_mode),.style(style),.origin_x(origin_x),
  .in_rgb(in_rgb),.in_valid(in_valid && !raw_mode),.in_ready(ci_ready),
  .out_rgb(co_rgb),.out_valid(co_valid),.out_ready(out_ready && !raw_mode),.done(cdone),
  .cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data));
 assign in_ready=raw_mode ? raw_running && out_ready:ci_ready;
 assign out_valid=raw_mode ? raw_running && in_valid:co_valid;
 assign out_rgb=raw_mode ? in_rgb:co_rgb;
 assign done=raw_mode ? raw_done:cdone;
 always @(posedge clk)begin
  raw_done<=0;
  if(reset)begin raw_running<=0;raw_count<=0;end
  else if(start)begin raw_running<=raw_mode;raw_count<=0;end
  else if(raw_mode && raw_running && in_valid && out_ready)begin
   if(raw_count==WIDTH*HEIGHT-1)begin raw_running<=0;raw_done<=1;end
   else raw_count<=raw_count+1'b1;
  end
 end
endmodule
