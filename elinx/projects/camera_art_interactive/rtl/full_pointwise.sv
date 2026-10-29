// Full-size 1x1: two output channels/clock, four pixel contexts.
// Constant-index input/result writers avoid dynamic 2D partial-write mapping.
module full_pointwise #(
 parameter CIN=6,COUT=6,LAYER=2,HEAD=0,RESIDUAL=1,LANES=2,CONTEXTS=4
)(input wire clk,reset,input wire[CIN*8-1:0]in_data,
 input wire[COUT*8-1:0]in_skip,input wire in_inside,in_valid,output wire in_ready,
 output wire[(HEAD?COUT*16:COUT*8)-1:0]out_data,output wire out_valid,input wire out_ready,output wire out_inside,
 input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);
 localparam AB=$clog2(CONTEXTS),OBITS=HEAD?COUT*16:COUT*8,NW=CIN*COUT;
 wire signed[7:0]weight[0:NW-1];wire signed[23:0]bias[0:COUT-1];wire[4:0]shift[0:COUT-1];
 wire[NW*8-1:0]fw;wire[COUT*24-1:0]fb;wire[COUT*5-1:0]fs;
 full_parameter_bank #(.LAYER(LAYER),.NW(NW),.COUT(COUT)) parameters(.clk(clk),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data),.weights(fw),.biases(fb),.shifts(fs));
 genvar n,c,l,k,s;
 generate for(n=0;n<NW;n=n+1)begin:weight_output assign weight[n]=fw[n*8+:8];end
 for(c=0;c<COUT;c=c+1)begin:channel_output assign bias[c]=fb[c*24+:24];assign shift[c]=fs[c*5+:5];end endgenerate
 reg[CONTEXTS-1:0]occupied,issued,finished,inside_hold;
 reg[AB-1:0]allocate_context,issue_context,retire_context;
 reg[CIN*8-1:0]pixels[0:CONTEXTS-1];reg[COUT*8-1:0]skip[0:CONTEXTS-1];
 reg[OBITS-1:0]result[0:CONTEXTS-1];reg[3:0]channel;
 reg[AB-1:0]context_tag[0:5];reg[3:0]tag[0:LANES-1][0:5];
 reg[5:0]valid_pipe[0:LANES-1];integer i,j;
 assign in_ready=!reset && !occupied[allocate_context];
 assign out_valid=!reset && finished[retire_context];
 assign out_data=result[retire_context];
 assign out_inside=inside_hold[retire_context];
 wire accept=in_valid && in_ready,retire=out_valid && out_ready;
 wire issue=occupied[issue_context] && !issued[issue_context];
 wire signed[22:0]q[0:LANES-1];
 generate for(l=0;l<LANES;l=l+1)begin:lane
  wire signed[16:0]products[0:7];
  for(k=0;k<8;k=k+1)begin:mul
   if(k<CIN)begin:used
    (* syn_use_dsp="yes" *)reg signed[16:0]p;
    always @(posedge clk)if(issue && channel+l<COUT)p<=$signed({1'b0,pixels[issue_context][k*8+:8]})*$signed(weight[(channel+l)*CIN+k]);
    assign products[k]=p;
   end else begin:unused assign products[k]=0;end
  end
  reg signed[17:0]a,b,c,d;reg signed[18:0]left,right;reg signed[19:0]sum;
  reg signed[22:0]rounded_sum,rounded_hold;
  assign q[l]=rounded_hold>>>shift[tag[l][5]];
  always @(posedge clk)begin
   if(valid_pipe[l][0])begin a<=$signed(products[0])+$signed(products[1]);b<=$signed(products[2])+$signed(products[3]);c<=$signed(products[4])+$signed(products[5]);d<=$signed(products[6])+$signed(products[7]);end
   if(valid_pipe[l][1])begin left<=a+b;right<=c+d;end
   if(valid_pipe[l][2])sum<=left+right;
   if(valid_pipe[l][3])rounded_sum<=$signed(sum)+$signed(bias[tag[l][3]])+(shift[tag[l][3]]==0?23'sd0:(23'sd1<<(shift[tag[l][3]]-1)));
   if(valid_pipe[l][4])rounded_hold<=rounded_sum;
  end
 end
 for(s=0;s<CONTEXTS;s=s+1)begin:context_writer
  always @(posedge clk)begin
   if(reset)begin pixels[s]<=0;skip[s]<=0;inside_hold[s]<=0;end
   else if(accept && allocate_context==s)begin pixels[s]<=in_data;skip[s]<=in_skip;inside_hold[s]<=in_inside;end
  end
  for(c=0;c<COUT;c=c+1)begin:channel_writer
   localparam LN=c%LANES;
   wire signed[22:0]hidden=q[LN]<0?0:q[LN]>255?255:q[LN];
   wire[8:0]sum={1'b0,hidden[7:0]}+(RESIDUAL?{1'b0,skip[s][c*8+:8]}:9'd0);
   if(HEAD)begin:head_writer
    always @(posedge clk)begin
     if(reset)result[s][c*16+:16]<=0;
     else if(valid_pipe[LN][5] && context_tag[5]==s && tag[LN][5]==c)
      result[s][c*16+:16]<=!inside_hold[s]?16'd0:q[LN]< -510?-16'sd510:q[LN]>510?16'sd510:q[LN][15:0];
    end
   end else begin:hidden_writer
    always @(posedge clk)begin
     if(reset)result[s][c*8+:8]<=0;
     else if(valid_pipe[LN][5] && context_tag[5]==s && tag[LN][5]==c)
      result[s][c*8+:8]<=!inside_hold[s]?8'd0:sum>255?8'd255:sum[7:0];
    end
   end
  end
 end endgenerate
 always @(posedge clk)begin
  context_tag[0]<=issue_context;for(i=1;i<6;i=i+1)context_tag[i]<=context_tag[i-1];
  for(j=0;j<LANES;j=j+1)begin
   valid_pipe[j]<={valid_pipe[j][4:0],issue && channel+j<COUT};
   tag[j][0]<=channel+j;for(i=1;i<6;i=i+1)tag[j][i]<=tag[j][i-1];
   if(valid_pipe[j][5] && tag[j][5]==COUT-1)finished[context_tag[5]]<=1;
  end
  if(accept)begin occupied[allocate_context]<=1;issued[allocate_context]<=0;finished[allocate_context]<=0;allocate_context<=allocate_context==CONTEXTS-1?0:allocate_context+1'b1;end
  if(issue)begin
   if(channel+LANES>=COUT)begin issued[issue_context]<=1;issue_context<=issue_context==CONTEXTS-1?0:issue_context+1'b1;channel<=0;end
   else channel<=channel+LANES;
  end
  if(retire)begin occupied[retire_context]<=0;finished[retire_context]<=0;retire_context<=retire_context==CONTEXTS-1?0:retire_context+1'b1;end
  if(reset)begin
   occupied<=0;issued<=0;finished<=0;allocate_context<=0;issue_context<=0;retire_context<=0;channel<=0;
   for(i=0;i<6;i=i+1)context_tag[i]<=0;
   for(j=0;j<LANES;j=j+1)begin valid_pipe[j]<=0;for(i=0;i<6;i=i+1)tag[j][i]<=0;end
  end
 end
endmodule
