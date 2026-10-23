// UI DMA remains 100MHz. Only the CNN runs on the added CORE_PLL output.
// Pixels cross atomic FIFOs; cfg/start use stable-data request/ACK mailboxes.
// No control bus is sampled without its synchronized request. Reset cancels
// all outstanding work; strip resets flush only streams/kernel, not weights.
module video_cnn_async #(
 parameter integer WIDTH=112,HEIGHT=720,FRAME_WIDTH=1280,
 parameter W0="",B0="",S0="",W1="",B1="",S1="",W2="",B2="",S2="",
 parameter W3="",B3="",S3="",W4="",B4="",S4=""
)(input wire clk,fast_clk,global_reset,reset,start,raw_mode,input wire[2:0]style,input wire signed[15:0]origin_x,
 input wire[23:0]in_rgb,input wire in_valid,output wire in_ready,
 output wire[23:0]out_rgb,output wire out_valid,input wire out_ready,output wire done,
 input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data,output wire cfg_ready);
 wire fast_reset,kernel_reset;
 reset_sync fast_domain(.clk(fast_clk),.async_reset(global_reset),.reset(fast_reset));
 reset_sync strip_domain(.clk(fast_clk),.async_reset(reset),.reset(kernel_reset));
 reg cfg_request,cfg_ack,start_request,done_toggle;
 reg[47:0]cfg_mail;reg[19:0]start_mail;
 (* async_reg="true",syn_srlstyle="registers" *)reg[1:0]cfg_ack_sync,done_sync;
 (* async_reg="true",syn_srlstyle="registers" *)reg[1:0]cfg_request_sync,start_request_sync;
 reg done_seen,cfg_seen,start_seen;
 reg[47:0]fast_cfg;reg fast_cfg_valid;
 reg[19:0]fast_start;reg fast_start_pulse,running;
 assign cfg_ready=cfg_request==cfg_ack_sync[1] && !global_reset;
 assign done=done_sync[1]!=done_seen;
 always @(posedge clk or posedge global_reset)begin
  if(global_reset)begin cfg_request<=0;start_request<=0;cfg_mail<=0;start_mail<=0;cfg_ack_sync<=0;done_sync<=0;done_seen<=0;end
  else begin
   cfg_ack_sync<={cfg_ack_sync[0],cfg_ack};done_sync<={done_sync[0],done_toggle};done_seen<=done_sync[1];
   if(cfg_valid && cfg_ready)begin cfg_mail<={cfg_address,cfg_data};cfg_request<=~cfg_request;end
   if(start)begin start_mail<={origin_x,style,raw_mode};start_request<=~start_request;end
  end
 end
 wire input_full,input_empty,input_wr_busy,input_rd_busy;
 wire output_full,output_empty,output_wr_busy,output_rd_busy;
 wire[23:0]fast_input,fast_output;wire fast_in_ready,fast_out_valid,fast_done;
 wire in_pop=running && !kernel_reset && !input_rd_busy && !input_empty && fast_in_ready;
 wire out_push=running && !kernel_reset && !output_wr_busy && !output_full && fast_out_valid;
 assign in_ready=!reset && !input_wr_busy && !input_full;
 assign out_valid=!reset && !output_rd_busy && !output_empty;
 stream_fifo_24 in_stream(.arst(reset),.wr_clk(clk),.rd_clk(fast_clk),.din(in_rgb),
  .wr_en(in_valid && in_ready),.rd_en(in_pop),.dout(fast_input),.full(input_full),.empty(input_empty),.wr_busy(input_wr_busy),.rd_busy(input_rd_busy));
 stream_fifo_24 out_stream(.arst(reset),.wr_clk(fast_clk),.rd_clk(clk),.din(fast_output),
  .wr_en(out_push),.rd_en(out_valid && out_ready),.dout(out_rgb),.full(output_full),.empty(output_empty),.wr_busy(output_wr_busy),.rd_busy(output_rd_busy));
 always @(posedge fast_clk)begin
  if(fast_reset)begin
   cfg_request_sync<=0;start_request_sync<=0;cfg_seen<=0;start_seen<=0;cfg_ack<=0;
   fast_cfg<=0;fast_cfg_valid<=0;fast_start<=0;fast_start_pulse<=0;running<=0;done_toggle<=0;
  end else begin
   cfg_request_sync<={cfg_request_sync[0],cfg_request};start_request_sync<={start_request_sync[0],start_request};
   fast_cfg_valid<=0;fast_start_pulse<=0;
   if(cfg_request_sync[1]!=cfg_seen)begin fast_cfg<=cfg_mail;fast_cfg_valid<=1;cfg_seen<=cfg_request_sync[1];end
   if(fast_cfg_valid)cfg_ack<=cfg_seen; // ACK only after the kernel write edge
   if(kernel_reset)running<=0;
   else if(start_request_sync[1]!=start_seen && !input_rd_busy && !output_wr_busy)begin
    fast_start<=start_mail;fast_start_pulse<=1;start_seen<=start_request_sync[1];running<=1;
   end
   if(running && fast_done)begin done_toggle<=~done_toggle;running<=0;end
  end
 end
 video_cnn_view_pipe #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.FRAME_WIDTH(FRAME_WIDTH),
  .W0(W0),.B0(B0),.S0(S0),.W1(W1),.B1(B1),.S1(S1),.W2(W2),.B2(B2),.S2(S2),
  .W3(W3),.B3(B3),.S3(S3),.W4(W4),.B4(B4),.S4(S4)) neural(
  .clk(fast_clk),.reset(kernel_reset),.start(fast_start_pulse),.raw_mode(fast_start[0]),.style(fast_start[3:1]),.origin_x(fast_start[19:4]),
  .in_rgb(fast_input),.in_valid(running && !input_empty && !input_rd_busy),.in_ready(fast_in_ready),
  .out_rgb(fast_output),.out_valid(fast_out_valid),.out_ready(!output_full && !output_wr_busy),.done(fast_done),
  .cfg_valid(fast_cfg_valid),.cfg_address(fast_cfg[47:32]),.cfg_data(fast_cfg[31:0]));
endmodule
