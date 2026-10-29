// One output-channel dot product per clock. Two pixel contexts retain input,
// skip, inside and completed outputs until consumption, so the six arithmetic
// pipeline stages need not drain between pixels. Context order is preserved.
module tiny_pointwise #(parameter COUT=8,LAYER=2,HEAD=0)(
 input wire clk,reset,input wire[63:0]in_data,in_skip,input wire in_inside,in_valid,output wire in_ready,
 output wire[(HEAD?COUT*16:COUT*8)-1:0]out_data,output wire out_valid,input wire out_ready,
 input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);
 localparam OBITS=HEAD?COUT*16:COUT*8;
 wire signed[7:0]weight[0:COUT*8-1];wire signed[23:0]bias[0:COUT-1];wire[4:0]shift[0:COUT-1];
 wire[COUT*64-1:0]frozen_weights;wire[COUT*24-1:0]frozen_biases;wire[COUT*5-1:0]frozen_shifts;
 generate if(HEAD)begin:shared
  tiny_shared_params #(.LAYER(LAYER),.NW(COUT*8),.COUT(COUT)) constants(.weights(frozen_weights),.biases(frozen_biases),.shifts(frozen_shifts));
 end endgenerate
 genvar n;
 generate for(n=0;n<COUT*8;n=n+1)begin:w_config
  if(HEAD)begin:constant assign weight[n]=frozen_weights[n*8+:8];end else begin:mutable
   reg signed[7:0]q;
   always @(posedge clk)if(cfg_valid && cfg_address[15:12]==LAYER && cfg_address[11:10]==0 && cfg_address[9:2]==n/4)q<=cfg_data[(n%4)*8+:8];
   assign weight[n]=q;
  end
 end
 for(n=0;n<COUT;n=n+1)begin:param_config
  if(HEAD)begin:constant assign bias[n]=frozen_biases[n*24+:24];assign shift[n]=frozen_shifts[n*5+:5];end else begin:mutable
   reg signed[23:0]b;reg[4:0]s;
   always @(posedge clk)if(cfg_valid && cfg_address[15:12]==LAYER && cfg_address[9:0]==n)begin
    if(cfg_address[11:10]==1)b<=cfg_data[23:0];
    if(cfg_address[11:10]==2)s<=cfg_data[4:0];
   end
   assign bias[n]=b;assign shift[n]=s;
  end
 end endgenerate

 reg[1:0]occupied,issued,finished,inside_hold;
 reg allocate_context,issue_context,retire_context;
 reg[63:0]pixels[0:1],skip[0:1];reg[OBITS-1:0]result[0:1];
 reg[3:0]channel;
 reg[5:0]valid_pipe,context_pipe;reg[3:0]tag[0:5];integer i;
 assign in_ready=!reset && !occupied[allocate_context];
 assign out_valid=!reset && finished[retire_context];
 assign out_data=result[retire_context];
 wire accept=in_valid && in_ready;
 wire retire=out_valid && out_ready;
 wire issue=occupied[issue_context] && !issued[issue_context];
 wire signed[17:0]product[0:7];
 generate for(n=0;n<8;n=n+1)begin:mul
  (* syn_use_dsp="yes" *)reg signed[17:0]p;
  always @(posedge clk)if(issue)p<=$signed({1'b0,pixels[issue_context][n*8+:8]})*$signed(weight[channel*8+n]);
  assign product[n]=p;
 end endgenerate
 reg signed[23:0]a,b,c,d,left,right,sum;
 reg signed[24:0]rounded_sum,rounded_hold;
 wire signed[24:0]q=rounded_hold>>>shift[tag[5]];
 wire signed[24:0]hidden=q<0?0:q>255?255:q;
 wire[8:0]residual={1'b0,hidden[7:0]}+{1'b0,skip[context_pipe[5]][tag[5]*8+:8]};
 always @(posedge clk)begin
  valid_pipe<={valid_pipe[4:0],issue};
  context_pipe<={context_pipe[4:0],issue_context};
  tag[0]<=channel;for(i=1;i<6;i=i+1)tag[i]<=tag[i-1];
  if(accept)begin
   occupied[allocate_context]<=1;issued[allocate_context]<=0;finished[allocate_context]<=0;
   allocate_context<=!allocate_context;
  end
  if(issue)begin
   if(channel==COUT-1)begin issued[issue_context]<=1;issue_context<=!issue_context;channel<=0;end
   else channel<=channel+1;
  end
  if(valid_pipe[0])begin a<=$signed(product[0])+$signed(product[1]);b<=$signed(product[2])+$signed(product[3]);c<=$signed(product[4])+$signed(product[5]);d<=$signed(product[6])+$signed(product[7]);end
  if(valid_pipe[1])begin left<=a+b;right<=c+d;end
  if(valid_pipe[2])sum<=left+right;
  if(valid_pipe[3])rounded_sum<=$signed(sum)+$signed(bias[tag[3]])+(shift[tag[3]]==0?33'sd0:(33'sd1<<(shift[tag[3]]-1)));
  if(valid_pipe[4])rounded_hold<=rounded_sum;
  if(valid_pipe[5] && tag[5]==COUT-1)finished[context_pipe[5]]<=1;
  if(retire)begin occupied[retire_context]<=0;finished[retire_context]<=0;retire_context<=!retire_context;end
  if(reset)begin
   occupied<=0;issued<=0;finished<=0;
   allocate_context<=0;issue_context<=0;retire_context<=0;channel<=0;valid_pipe<=0;context_pipe<=0;
   for(i=0;i<6;i=i+1)tag[i]<=0;
  end
 end
 genvar slot,out_channel;
 generate for(slot=0;slot<2;slot=slot+1)begin:fixed_context
  always @(posedge clk)begin
   if(reset)begin pixels[slot]<=0;skip[slot]<=0;inside_hold[slot]<=0;end
   else if(accept && allocate_context==slot)begin pixels[slot]<=in_data;skip[slot]<=in_skip;inside_hold[slot]<=in_inside;end
  end
  for(out_channel=0;out_channel<COUT;out_channel=out_channel+1)begin:fixed_channel
   if(HEAD)begin:head_writer
    always @(posedge clk)begin
     if(reset)result[slot][out_channel*16+:16]<=0;
     else if(valid_pipe[5] && context_pipe[5]==slot && tag[5]==out_channel)
      result[slot][out_channel*16+:16]<=!inside_hold[slot]?16'd0:q< -510?-16'sd510:q>510?16'sd510:q[15:0];
    end
   end else begin:hidden_writer
    always @(posedge clk)begin
     if(reset)result[slot][out_channel*8+:8]<=0;
     else if(valid_pipe[5] && context_pipe[5]==slot && tag[5]==out_channel)
      result[slot][out_channel*8+:8]<=!inside_hold[slot]?8'd0:residual>255?8'd255:residual[7:0];
    end
   end
  end
 end endgenerate
endmodule
