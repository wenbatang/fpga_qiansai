// Fold output channels over LANES MAC lanes. Weights and arithmetic are exact.
// Real image boundaries reflect101 at EVERY layer; artificial strip edges zero.
module fps12_conv3x3 #(
 parameter WIDTH=128,HEIGHT=720,FRAME_WIDTH=1280,CIN=12,COUT=12,DILATION=1,
 parameter LANES=3,STYLE_COUNT=1,
 parameter WEIGHT_FILE="",BIAS_FILE="",SHIFT_FILE=""
)(input wire clk,reset,start,input wire[2:0]style,input wire signed[15:0]origin_x,
 input wire[CIN*8-1:0]in_data,input wire in_valid,output wire in_ready,
 output reg[COUT*8-1:0]out_data,output reg out_valid,input wire out_ready,output reg done,input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);
 localparam PW=WIDTH+2*DILATION,PH=HEIGHT+2*DILATION,ROWS=2*DILATION+1;
 localparam GROUPS=(COUT+LANES-1)/LANES,GB=GROUPS>1?$clog2(GROUPS):1;
 localparam RB=$clog2(ROWS),AB=$clog2(ROWS*WIDTH),WB=$clog2(STYLE_COUNT*GROUPS*9);
 localparam BB=STYLE_COUNT*GROUPS>1?$clog2(STYLE_COUNT*GROUPS):1;
 localparam IDLE=0,FEED=1,TAPS=2,DRAIN=3,EMIT=4;
 reg[2:0]state,style_hold;reg[15:0]px,py;reg[RB-1:0]row_ptr;
 reg[3:0]tap;reg[GB-1:0]group_no;reg signed[15:0]origin;
 wire actual=px>=DILATION && px<WIDTH+DILATION && py>=DILATION && py<HEIGHT+DILATION;
 wire step=!out_valid || out_ready;
 assign in_ready=state==FEED && actual && step;
 wire signed[17:0]center_global=$signed(origin)+$signed({1'b0,px})-2*DILATION;
 wire center_inside=center_global>=0 && center_global<FRAME_WIDTH;
 reg[1:0]kr,kc;reg signed[17:0] raw_local,global_sample,local_sample,raw_y;
 reg[RB-1:0]lag;
 always @*begin
  case(tap)
   0:begin kr=0;kc=0;end 1:begin kr=0;kc=1;end 2:begin kr=0;kc=2;end
   3:begin kr=1;kc=0;end 4:begin kr=1;kc=1;end 5:begin kr=1;kc=2;end
   6:begin kr=2;kc=0;end 7:begin kr=2;kc=1;end 8:begin kr=2;kc=2;end
   default:begin kr=0;kc=0;end
  endcase
  raw_local=px-3*DILATION+kc*DILATION;
  global_sample=$signed(origin)+raw_local;
  if(global_sample<0)global_sample=FRAME_WIDTH>DILATION ? -global_sample:0;
  else if(global_sample>=FRAME_WIDTH)global_sample=FRAME_WIDTH>DILATION ? 2*(FRAME_WIDTH-1)-global_sample:FRAME_WIDTH-1;
  local_sample=global_sample-$signed(origin);
  raw_y=0;
  if(HEIGHT>DILATION)case(kr)
   0:lag=py<3*DILATION ? (py-2*DILATION)<<1:2*DILATION;
   1:lag=DILATION;
   default:lag=py>=HEIGHT+DILATION ? (py-(HEIGHT+DILATION-1))<<1:0;
  endcase
  else begin
   raw_y=py-2*DILATION+kr*DILATION;
   if(raw_y<DILATION)raw_y=DILATION;
   else if(raw_y>=HEIGHT+DILATION)raw_y=HEIGHT+DILATION-1;
   lag=py-raw_y;
  end
 end
 wire[RB:0]delta={1'b0,row_ptr}-{1'b0,lag};
 wire[RB-1:0]read_row=delta[RB]?delta+ROWS:delta;
 (* syn_use_dsp="no",use_dsp="no" *) wire[AB-1:0]row_base,write_base;
 assign row_base=read_row*WIDTH;assign write_base=row_ptr*WIDTH;
 wire[AB-1:0]write_address=write_base+px-DILATION;
 wire sample_valid=center_inside && local_sample>=0 && local_sample<WIDTH;
 wire[AB-1:0]mapped_address=row_base+local_sample;
 reg[AB-1:0]read_address;
 reg[WB-1:0]weight_address;reg[BB-1:0]bias_address;
 reg sample_address_ok,sample_ok;
 wire[CIN*8-1:0]sample;
 reg[5:0]valid_pipe,first_pipe,last_pipe;
 reg[GB-1:0]group_pipe[0:5];integer p,j;
 fps12_line_ram #(.DATA_BITS(CIN*8),.DEPTH(ROWS*WIDTH)) history(
 .clk(clk),.write_enable(!reset && step && state==FEED && actual && in_valid),
 .write_address(write_address),.write_data(actual?in_data:{CIN*8{1'b0}}),
 .read_enable(step && valid_pipe[0] && sample_address_ok),.read_address(read_address),.read_data(sample));
 wire[CIN*LANES*8-1:0]weights_read;
 // Only 4/16 words: a synchronous logic ROM avoids wasting wide RAM10 blocks.
 // Keep the same read register and all five bias pipeline stages.
 (* syn_ramstyle="registers" *) reg[LANES*32-1:0]biases[0:STYLE_COUNT*GROUPS-1];
 reg[7:0]shifts[0:STYLE_COUNT-1];
 reg[32:0]rounding;reg[5:0]inside_pipe;
 reg quant_inside,round_inside,round_valid;reg[GB-1:0]round_group;reg[31:0]emitted;
 reg[CIN*LANES*8-1:0]weight_word;reg[LANES*32-1:0]bias_pipe[1:5];
 localparam CHUNKS=(CIN*LANES*8+31)/32;
 reg[CHUNKS*32-1:0] assembly;
 wire[5:0]cfg_word=cfg_address[10:5];
 wire[4:0]cfg_chunk=cfg_address[4:0];
 fps12_srl_weights #(.DATA_BITS(CIN*LANES*8),.WORDS(STYLE_COUNT*GROUPS*9)) weights(
  .clk(clk),.write_enable(cfg_valid && cfg_address[15:14]==0 && cfg_word<GROUPS*9 && cfg_chunk==CHUNKS-1),
  .write_address(cfg_word[WB-1:0]),.write_data({cfg_data,assembly[CHUNKS*32-33:0]}),
  .read_address(weight_address),.read_data(weights_read));
 always @(posedge clk)if(cfg_valid)begin
  if(cfg_address[15:14]==0 && cfg_word<GROUPS*9 && cfg_chunk<CHUNKS)begin
   assembly[cfg_chunk*32+:32]<=cfg_data;

  end
  if(cfg_address[15:14]==2 && cfg_data<=31)begin
   shifts[0]<={3'd0,cfg_data[4:0]};rounding<=cfg_data==0 ? 33'd0:(33'd1<<(cfg_data[4:0]-1));
  end
 end
 // Fixed channel decoders avoid a dynamically indexed word AND dynamic
 // subword write in the same bias assignment. The old form is numerically
 // correct in RTL but the installed mapper misroutes some channel writes.
 // Every physical 32-bit slice now has exactly one constant-index writer.
 genvar bias_channel;
 generate for(bias_channel=0;bias_channel<COUT;bias_channel=bias_channel+1)begin:bias_config
  always @(posedge clk)if(cfg_valid && cfg_address[15:14]==1 && cfg_address[10:0]==bias_channel)
   biases[bias_channel/LANES][(bias_channel%LANES)*32+:32]<=cfg_data;
 end endgenerate
 always @(posedge clk)if(step)begin
  if(state==TAPS)begin
   read_address<=mapped_address;sample_address_ok<=sample_valid;
   weight_address<=(group_no)*9+tap;
   bias_address<=group_no;
  end
  if(valid_pipe[0])begin
   weight_word<=weights_read;bias_pipe[1]<=biases[bias_address];sample_ok<=sample_address_ok;
  end
  for(p=2;p<6;p=p+1)if(valid_pipe[p-1])bias_pipe[p]<=bias_pipe[p-1];
 end
 wire signed[17:0]products[0:LANES*CIN-1];
 genvar n,o,k;
 generate for(n=0;n<LANES*CIN;n=n+1)begin:mul
  if(CIN==3)begin:logic_product
   // Nine first-layer multiplies use spare logic, leaving DSP headroom.
   // Full signed product, clock enable and pipeline latency are unchanged.
   (* syn_use_dsp="no",use_dsp="no" *)reg signed[17:0]q;
   always @(posedge clk)if(step && valid_pipe[1])q<=$signed({1'b0,(sample_ok ? sample[(n%CIN)*8+:8]:8'd0)})*$signed(weight_word[n*8+:8]);
   assign products[n]=q;
  end else begin:dsp_product
   (* syn_use_dsp="yes",use_dsp="yes" *)reg signed[17:0]q;
   always @(posedge clk)if(step && valid_pipe[1])q<=$signed({1'b0,(sample_ok ? sample[(n%CIN)*8+:8]:8'd0)})*$signed(weight_word[n*8+:8]);
   assign products[n]=q;
  end
 end endgenerate
 reg quant_valid;reg[GB-1:0]quant_group;wire[7:0]quantized[0:LANES-1];
 generate for(o=0;o<LANES;o=o+1)begin:lane
  wire signed[31:0]pairs[0:5];
  for(k=0;k<6;k=k+1)begin:pair
   reg signed[31:0]q;
   if(2*k+1<CIN)begin:two
    always @(posedge clk)if(step && valid_pipe[2])q<=$signed(products[o*CIN+2*k])+$signed(products[o*CIN+2*k+1]);
   end else if(2*k<CIN)begin:one
    always @(posedge clk)if(step && valid_pipe[2])q<=products[o*CIN+2*k];
   end else begin:zero
    always @(posedge clk)if(step && valid_pipe[2])q<=0;
   end
   assign pairs[k]=q;
  end
  reg signed[31:0]left,right,dot,accumulator,completed;
  wire signed[31:0]base=first_pipe[5]?$signed(bias_pipe[5][o*32+:32]):accumulator;
  wire signed[31:0]sum=base+dot;
  wire signed[32:0]wide={{1{completed[31]}},completed};
  reg signed[32:0]rounded_sum;
  wire signed[32:0]rounded=rounded_sum>>>shifts[0][4:0];
  always @(posedge clk)begin
   if(step && quant_valid)rounded_sum<=wide+$signed(rounding);
   if(step && valid_pipe[3])begin left<=(pairs[0]+pairs[1])+pairs[2];right<=(pairs[3]+pairs[4])+pairs[5];end
   if(step && valid_pipe[4])dot<=left+right;
   if(reset)accumulator<=0;
   else if(step && valid_pipe[5])begin accumulator<=sum;if(last_pipe[5])completed<=sum;end
  end
  assign quantized[o]=!round_inside || rounded<0 ? 8'd0:rounded>255 ? 8'd255:rounded[7:0];
 end endgenerate
 task automatic advance;
 begin
  if(px==PW-1)begin
   px<=0;row_ptr<=row_ptr==ROWS-1?0:row_ptr+1'b1;
   if(py==PH-1)begin state<=DRAIN;end else begin py<=py+1;state<=FEED;end
  end else begin px<=px+1;state<=FEED;end
 end
 endtask
 // Issue the next pixel immediately after its final tap. Global step
 // freezes every data/control stage under output backpressure. Rounding
 // addition and barrel shift/saturation now occupy separate pipeline stages.
 always @(posedge clk)begin
  done<=0;
  if(step)begin
   quant_valid<=valid_pipe[5] && last_pipe[5];
   if(valid_pipe[5] && last_pipe[5])begin quant_group<=group_pipe[5];quant_inside<=inside_pipe[5];end
   round_valid<=quant_valid;
   if(quant_valid)begin round_group<=quant_group;round_inside<=quant_inside;end
   valid_pipe<={valid_pipe[4:0],state==TAPS};
   first_pipe<={first_pipe[4:0],state==TAPS && tap==0};
   last_pipe<={last_pipe[4:0],state==TAPS && tap==8};
   inside_pipe<={inside_pipe[4:0],center_inside};
   group_pipe[0]<=group_no;
   for(j=1;j<6;j=j+1)group_pipe[j]<=group_pipe[j-1];
   if(round_valid)for(j=0;j<LANES;j=j+1)
    if(round_group*LANES+j<COUT)out_data[(round_group*LANES+j)*8+:8]<=quantized[j];
   if(out_valid && out_ready)begin
    out_valid<=0;
    if(emitted==WIDTH*HEIGHT-1)begin done<=1;state<=IDLE;end
    else emitted<=emitted+1'b1;
   end
   if(round_valid && round_group==GROUPS-1)out_valid<=1;
   case(state)
    IDLE:if(start)begin state<=FEED;px<=0;py<=0;row_ptr<=0;origin<=origin_x;style_hold<=style<STYLE_COUNT?style:0;out_valid<=0;emitted<=0;end
    FEED:if(!actual || in_valid)begin
     if(px>=2*DILATION && py>=2*DILATION)begin tap<=0;group_no<=0;state<=TAPS;end
     else advance();
    end
    TAPS:if(tap==8)begin
     tap<=0;if(group_no==GROUPS-1)advance();else group_no<=group_no+1'b1;
    end else tap<=tap+1'b1;
    DRAIN:begin end
    default:state<=IDLE;
   endcase
  end
  if(reset)begin
   state<=IDLE;px<=0;py<=0;row_ptr<=0;tap<=0;group_no<=0;style_hold<=0;origin<=0;
   valid_pipe<=0;first_pipe<=0;last_pipe<=0;inside_pipe<=0;out_valid<=0;quant_valid<=0;round_valid<=0;
   quant_inside<=0;round_inside<=0;round_group<=0;out_data<=0;emitted<=0;
  end
 end
endmodule
