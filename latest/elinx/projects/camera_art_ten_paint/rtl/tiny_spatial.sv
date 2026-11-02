// 8-wide stem or depthwise 3x3. One tap/cycle; BRAM history, exact int32 MAC.
// The scan/reflect101 row addressing derives from camera_720_fast's audited
// video_conv3x3_pipe. Only true frame borders reflect; artificial strip edges zero.
module tiny_spatial #(
 parameter WIDTH=96,HEIGHT=360,FRAME_WIDTH=640,CIN=8,COUT=8,DILATION=1,DW=1,LAYER=1
)(input wire clk,reset,start,input wire signed[15:0]origin_x,
 input wire[CIN*8-1:0]in_data,input wire in_valid,output wire in_ready,
 output reg[COUT*8-1:0]out_data,output reg[CIN*8-1:0]out_center,
 output reg out_inside,out_valid,input wire out_ready,
 input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);
 localparam PW=WIDTH+2*DILATION,PH=HEIGHT+2*DILATION,ROWS=2*DILATION+1;
 localparam RB=$clog2(ROWS),AB=$clog2(ROWS*WIDTH);
 localparam IDLE=0,FEED=1,TAPS=2,DRAIN=3;
 reg[1:0]state;reg[15:0]px,py;reg[RB-1:0]row_ptr;reg[3:0]tap;
 reg signed[15:0]origin;
 wire actual=px>=DILATION && px<WIDTH+DILATION && py>=DILATION && py<HEIGHT+DILATION;
 wire step=!out_valid || out_ready;
 assign in_ready=state==FEED && actual && step;
 wire signed[17:0]center_global=$signed(origin)+$signed({1'b0,px})-2*DILATION;
 wire center_inside=center_global>=0 && center_global<FRAME_WIDTH;
 reg[1:0]kr,kc;integer raw_local,global_sample,local_sample,raw_y;
 reg[RB-1:0]lag;
 always @*begin
  case(tap)
   0:begin kr=0;kc=0;end 1:begin kr=0;kc=1;end 2:begin kr=0;kc=2;end
   3:begin kr=1;kc=0;end 4:begin kr=1;kc=1;end 5:begin kr=1;kc=2;end
   6:begin kr=2;kc=0;end 7:begin kr=2;kc=1;end default:begin kr=2;kc=2;end
  endcase
  raw_local=px-3*DILATION+kc*DILATION;
  global_sample=$signed(origin)+raw_local;
  if(global_sample<0)global_sample=FRAME_WIDTH>DILATION ? -global_sample:0;
  else if(global_sample>=FRAME_WIDTH)global_sample=FRAME_WIDTH>DILATION ? 2*(FRAME_WIDTH-1)-global_sample:FRAME_WIDTH-1;
  local_sample=global_sample-$signed(origin);raw_y=0;
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
 (* syn_use_dsp="no" *)wire[AB-1:0]row_base=read_row*WIDTH,write_base=row_ptr*WIDTH;
 wire[AB-1:0]write_address=write_base+px-DILATION,mapped_address=row_base+local_sample;
 wire sample_valid=center_inside && local_sample>=0 && local_sample<WIDTH;
 reg[AB-1:0]read_address;reg[3:0]weight_address;
 reg sample_address_ok,sample_ok;wire[CIN*8-1:0]sample;
 reg[5:0]valid_pipe,first_pipe,last_pipe,inside_pipe,center_pipe;
 reg[CIN*8-1:0]center_store,quant_center,round_center;
 reg quant_valid,round_valid,quant_inside,round_inside;reg[31:0]emitted;
 style_line_ram #(.DATA_BITS(CIN*8),.DEPTH(ROWS*WIDTH)) history(
 .clk(clk),.write_enable(!reset && step && state==FEED && actual && in_valid),
 .write_address(write_address),.write_data(in_data),
 .read_enable(step && valid_pipe[0] && sample_address_ok),.read_address(read_address),.read_data(sample));
 localparam NW=COUT*(DW?1:CIN)*9;
 wire signed[7:0]weight[0:NW-1];wire signed[23:0]bias[0:COUT-1];wire[4:0]shift[0:COUT-1];
 wire[NW*8-1:0]frozen_weights;wire[COUT*24-1:0]frozen_biases;wire[COUT*5-1:0]frozen_shifts;
 generate if(DW)begin:shared
  tiny_shared_params #(.LAYER(LAYER),.NW(NW),.COUT(COUT)) constants(.weights(frozen_weights),.biases(frozen_biases),.shifts(frozen_shifts));
 end endgenerate
 genvar n,o,k;
 generate for(n=0;n<NW;n=n+1)begin:w_config
  if(DW)begin:constant assign weight[n]=frozen_weights[n*8+:8];end else begin:mutable
  reg signed[7:0]q;
  always @(posedge clk)if(cfg_valid && cfg_address[15:12]==LAYER && cfg_address[11:10]==0 && cfg_address[9:2]==n/4)q<=cfg_data[(n%4)*8+:8];
  assign weight[n]=q;
  end
 end
 for(o=0;o<COUT;o=o+1)begin:param_config
  if(DW)begin:constant assign bias[o]=frozen_biases[o*24+:24];assign shift[o]=frozen_shifts[o*5+:5];end else begin:mutable
  reg signed[23:0]b;reg[4:0]s;
  always @(posedge clk)if(cfg_valid && cfg_address[15:12]==LAYER && cfg_address[9:0]==o)begin
   if(cfg_address[11:10]==1)b<=cfg_data[23:0];
   if(cfg_address[11:10]==2)s<=cfg_data[4:0];
  end
  assign bias[o]=b;assign shift[o]=s;
  end
 end endgenerate
 reg[(DW?COUT:COUT*CIN)*8-1:0]weight_word;integer p;
 always @(posedge clk)if(step)begin
  if(state==TAPS)begin read_address<=mapped_address;sample_address_ok<=sample_valid;weight_address<=tap;end
  if(valid_pipe[0])begin sample_ok<=sample_address_ok;end
  if(valid_pipe[1] && center_pipe[1])center_store<=sample;
 end
 generate for(o=0;o<COUT;o=o+1)begin:mac
  wire signed[17:0]products[0:7];
  for(k=0;k<8;k=k+1)begin:mul
   if(k<CIN && (!DW || o==k))begin:used
    reg signed[7:0]w;(* syn_use_dsp="yes" *)reg signed[17:0]q;
    always @(posedge clk)if(step)begin
     if(valid_pipe[0])w<=weight[(DW?o:o*CIN+k)*9+weight_address];
     if(valid_pipe[1])q<=$signed({1'b0,sample_ok?sample[k*8+:8]:8'd0})*$signed(w);
    end
    assign products[k]=q;
   end else begin:unused assign products[k]=0;end
  end
  reg signed[23:0]pair0,pair1,pair2,pair3,left,right,dot,acc,completed;
  wire signed[23:0]base=first_pipe[5]?bias[o]:acc;
  wire signed[23:0]sum=base+dot;
  reg signed[24:0]rounded_sum;
  wire signed[24:0]rounded=rounded_sum>>>shift[o];
  always @(posedge clk)begin
   if(step && valid_pipe[2])begin
    pair0<=$signed(products[0])+$signed(products[1]);
    pair1<=$signed(products[2])+$signed(products[3]);
    pair2<=$signed(products[4])+$signed(products[5]);
    pair3<=$signed(products[6])+$signed(products[7]);
   end
   if(step && valid_pipe[3])begin left<=pair0+pair1;right<=pair2+pair3;end
   if(step && valid_pipe[4])dot<=left+right;
   if(reset)acc<=0;else if(step && valid_pipe[5])begin acc<=sum;if(last_pipe[5])completed<=sum;end
   if(step && quant_valid)rounded_sum<={{1{completed[23]}},completed}+(shift[o]==0?25'sd0:(25'sd1<<(shift[o]-1)));
   if(step && round_valid)out_data[o*8+:8]<=!round_inside || rounded<0?8'd0:rounded>255?8'd255:rounded[7:0];
  end
 end endgenerate
 task automatic advance;
 begin
  if(px==PW-1)begin px<=0;row_ptr<=row_ptr==ROWS-1?0:row_ptr+1'b1;
   if(py==PH-1)state<=DRAIN;else begin py<=py+1;state<=FEED;end
  end else begin px<=px+1;state<=FEED;end
 end endtask
 always @(posedge clk)begin
  if(step)begin
   valid_pipe<={valid_pipe[4:0],state==TAPS};first_pipe<={first_pipe[4:0],state==TAPS && tap==0};last_pipe<={last_pipe[4:0],state==TAPS && tap==8};
   inside_pipe<={inside_pipe[4:0],center_inside};center_pipe<={center_pipe[4:0],state==TAPS && tap==4};
   quant_valid<=valid_pipe[5] && last_pipe[5];
   if(valid_pipe[5] && last_pipe[5])begin quant_inside<=inside_pipe[5];quant_center<=center_store;end
   round_valid<=quant_valid;
   if(quant_valid)begin round_inside<=quant_inside;round_center<=quant_center;end
   if(round_valid)begin out_valid<=1;out_inside<=round_inside;out_center<=round_center;end
   else if(out_valid && out_ready)begin out_valid<=0;emitted<=emitted+1;if(emitted==WIDTH*HEIGHT-1)state<=IDLE;end
   case(state)
    IDLE:if(start)begin state<=FEED;px<=0;py<=0;row_ptr<=0;origin<=origin_x;out_valid<=0;emitted<=0;end
    FEED:if(!actual || in_valid)begin if(px>=2*DILATION && py>=2*DILATION)begin tap<=0;state<=TAPS;end else advance();end
    TAPS:if(tap==8)begin tap<=0;advance();end else tap<=tap+1;
    default:begin end
   endcase
  end
  if(reset)begin state<=IDLE;px<=0;py<=0;row_ptr<=0;tap<=0;origin<=0;valid_pipe<=0;first_pipe<=0;last_pipe<=0;inside_pipe<=0;center_pipe<=0;out_valid<=0;quant_valid<=0;round_valid<=0;quant_inside<=0;round_inside<=0;out_inside<=0;emitted<=0;out_center<=0;quant_center<=0;round_center<=0;end
 end
endmodule
