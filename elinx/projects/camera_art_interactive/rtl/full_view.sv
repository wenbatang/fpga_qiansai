module full_view #(parameter WIDTH=352,HEIGHT=720,FRAME_WIDTH=1280)(
 input wire clk,reset,start,raw_mode,input wire signed[15:0]origin_x,
 input wire[23:0]in_rgb,input wire in_valid,output wire in_ready,
 output wire[23:0]out_rgb,output wire out_valid,input wire out_ready,output wire done,
 input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data,input wire split_mode);
 wire ci_ready,co_valid,cdone;wire[23:0]co_rgb;reg raw_running,raw_done;reg[31:0]raw_count;
 full_kernel #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.FRAME_WIDTH(FRAME_WIDTH)) neural(
 .clk(clk),.reset(reset),.start(start && !raw_mode),.origin_x(origin_x),.in_rgb(in_rgb),.in_valid(in_valid && !raw_mode),.in_ready(ci_ready),.out_rgb(co_rgb),.out_valid(co_valid),.out_ready(out_ready && !raw_mode),.done(cdone),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data),.split_mode(split_mode));
 assign in_ready=raw_mode?raw_running && out_ready:ci_ready;
 assign out_valid=raw_mode?raw_running && in_valid:co_valid;
 assign out_rgb=raw_mode?in_rgb:co_rgb;
 assign done=raw_mode?raw_done:cdone;
 always @(posedge clk)begin
  raw_done<=0;
  if(reset)begin raw_running<=0;raw_count<=0;end
  else if(start)begin raw_running<=raw_mode;raw_count<=0;end
  else if(raw_mode && raw_running && in_valid && out_ready)begin
   if(raw_count==WIDTH*HEIGHT-1)begin raw_running<=0;raw_done<=1;end else raw_count<=raw_count+1;
  end
 end
endmodule
