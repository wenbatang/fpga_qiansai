// Three taps/clock, column-interleaved BRAM banks (no history replication).
// D=1/2/4/8 gives distinct banks in the interior. Reflect101 borders can
// conflict: a second read phase gathers the missing address before the MAC.
module full_dw3x3 #(
 parameter WIDTH=352,HEIGHT=720,FRAME_WIDTH=1280,CHANNELS=6,DILATION=1,LAYER=1
)(input wire clk,reset,start,input wire signed[15:0]origin_x,
 input wire[CHANNELS*8-1:0]in_data,input wire in_valid,output wire in_ready,
 output reg[CHANNELS*8-1:0]out_data,out_center,output reg out_inside,out_valid,input wire out_ready,
 input wire cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data);
 localparam PW=WIDTH+2*DILATION,PH=HEIGHT+2*DILATION,ROWS=2*DILATION+1;
 localparam COLS=(WIDTH+2)/3,RB=$clog2(ROWS),AB=$clog2(ROWS*COLS);
 localparam XB=$clog2(PW),YB=$clog2(PH),LB=WIDTH>1?$clog2(WIDTH):1,CB=COLS>1?$clog2(COLS):1;
 localparam IDLE=0,FEED=1,READ=2,DRAIN=3;
 reg[1:0]state,row_select;reg second_phase;reg[XB-1:0]px;reg[YB-1:0]py;reg[RB-1:0]row_ptr;
 reg signed[15:0]origin;
 wire step=!out_valid || out_ready;
 wire actual=px>=DILATION && px<WIDTH+DILATION && py>=DILATION && py<HEIGHT+DILATION;
 assign in_ready=state==FEED && actual && step;
 wire signed[17:0]center_global=$signed(origin)+$signed({1'b0,px})-2*DILATION;
 wire center_inside=center_global>=0 && center_global<FRAME_WIDTH;
 function automatic[AB-1:0]scaled_row(input[RB-1:0]r);
  integer bit_index;reg[AB-1:0]total;
  begin total=0;for(bit_index=0;bit_index<$clog2(COLS+1);bit_index=bit_index+1)
   if((COLS>>bit_index)&1)total=total+({{(AB-RB){1'b0}},r}<<bit_index);
   scaled_row=total;
  end
 endfunction
 function automatic[AB-1:0]base_for(input[1:0]which);
  reg[RB-1:0]lg,r;reg[RB:0]delta;integer raw_y;
  begin
   raw_y=0;
   if(HEIGHT>DILATION)case(which)
    0:lg=py<3*DILATION?(py-2*DILATION)<<1:2*DILATION;
    1:lg=DILATION;
    default:lg=py>=HEIGHT+DILATION?(py-(HEIGHT+DILATION-1))<<1:0;
   endcase
   else begin
    raw_y=py-2*DILATION+which*DILATION;
    if(raw_y<DILATION)raw_y=DILATION;else if(raw_y>=HEIGHT+DILATION)raw_y=HEIGHT+DILATION-1;
    lg=py-raw_y;
   end
   delta={1'b0,row_ptr}-{1'b0,lg};r=delta[RB]?delta+ROWS:delta;
   base_for=scaled_row(r);
  end
 endfunction
 (* syn_use_dsp="no" *)reg[AB-1:0]row_bases[0:2],write_base;
 wire[AB-1:0]read_base=row_bases[row_select];
 wire[LB-1:0]write_x=px-DILATION;
 wire[AB-1:0]write_address=write_base+write_x/3;
 // Compute the next horizontal mapping one pixel ahead. Two registered
 // stages split global reflect arithmetic from bank/conflict selection.
 // Prediction is available on the final READ edge; FEED finishes stage2
 // before the first RAM read, retaining the four-clock interior interval.
 reg need_second;
 wire feed_advance=state==FEED && (!actual || in_valid) && !(px>=2*DILATION && py>=2*DILATION);
 wire read_advance=state==READ && row_select==2 && (!need_second || second_phase);
 wire[XB-1:0]predict_px=(feed_advance || read_advance)?(px==PW-1?{XB{1'b0}}:px+1'b1):px;
 wire signed[17:0]predict_center=$signed(origin)+$signed({1'b0,predict_px})-2*DILATION;
 wire predict_inside=predict_center>=0 && predict_center<FRAME_WIDTH;
 reg[LB-1:0]mapped_local[0:2];reg[2:0]mapped_valid;reg mapped_inside;
 reg[XB-1:0]mapped_px,sample_px;
 reg[2:0]first_enable,second_enable,first_mask,second_mask,sample_valid;
 reg[CB-1:0]first_column[0:2],second_column[0:2];reg[1:0]sample_bank[0:2];reg sample_inside;
 reg[2:0]nx_first_enable,nx_second_enable,nx_first_mask,nx_second_mask;
 reg[CB-1:0]nx_first_column[0:2],nx_second_column[0:2],nx_column[0:2];reg[1:0]nx_bank[0:2];
 integer k,b;
 always @*begin
  nx_first_enable=0;nx_second_enable=0;nx_first_mask=0;nx_second_mask=0;
  for(b=0;b<3;b=b+1)begin nx_first_column[b]=0;nx_second_column[b]=0;end
  for(k=0;k<3;k=k+1)begin
   nx_bank[k]=mapped_local[k]%3;nx_column[k]=mapped_local[k]/3;
   if(mapped_valid[k])begin
    if(!nx_first_enable[nx_bank[k]])begin nx_first_enable[nx_bank[k]]=1;nx_first_column[nx_bank[k]]=nx_column[k];end
    else if(nx_first_column[nx_bank[k]]!=nx_column[k])begin nx_second_enable[nx_bank[k]]=1;nx_second_column[nx_bank[k]]=nx_column[k];end
   end
  end
  for(k=0;k<3;k=k+1)if(mapped_valid[k])begin
   if(nx_column[k]==nx_first_column[nx_bank[k]])nx_first_mask[k]=1;else nx_second_mask[k]=1;
  end
 end
 wire[2:0]bank_enable=second_phase?second_enable:first_enable;
 wire[2:0]request_mask=second_phase?second_mask:first_mask;
 wire[AB-1:0]bank_address[0:2];
 genvar horizontal;
 generate for(horizontal=0;horizontal<3;horizontal=horizontal+1)begin:horizontal_map
  wire signed[17:0]local_pre=$signed({1'b0,predict_px})-3*DILATION+horizontal*DILATION;
  wire signed[17:0]global_pre=$signed(origin)+local_pre;
  wire signed[17:0]reflected=global_pre<0?(FRAME_WIDTH>DILATION?-global_pre:0):global_pre>=FRAME_WIDTH?(FRAME_WIDTH>DILATION?2*(FRAME_WIDTH-1)-global_pre:FRAME_WIDTH-1):global_pre;
  wire signed[17:0]local_next=reflected-$signed(origin);
  always @(posedge clk)begin
   if(step)begin mapped_local[horizontal]<=local_next[LB-1:0];mapped_valid[horizontal]<=predict_inside && local_next>=0 && local_next<WIDTH;end
   if(reset || start)begin mapped_local[horizontal]<=0;mapped_valid[horizontal]<=0;end
  end
  assign bank_address[horizontal]=read_base+(second_phase?second_column[horizontal]:first_column[horizontal]);
 end endgenerate
 wire[CHANNELS*8-1:0]bank_data[0:2];
 genvar bank,c,t;
 generate for(bank=0;bank<3;bank=bank+1)begin:history_bank
  style_line_ram #(.DATA_BITS(CHANNELS*8),.DEPTH(ROWS*COLS)) memory(
   .clk(clk),.write_enable(!reset && step && state==FEED && actual && in_valid && write_x%3==bank),
   .write_address(write_address),.write_data(in_data),.read_enable(step && state==READ && bank_enable[bank]),
   .read_address(bank_address[bank]),.read_data(bank_data[bank]));
 end endgenerate
 reg rd_valid,rd_complete,rd_inside;reg[1:0]rd_row;
 reg[2:0]rd_mask,rd_sample_valid;reg[1:0]rd_bank[0:2];
 reg[CHANNELS*8-1:0]partial[0:2],center_store,quant_center,round_center;
 wire[CHANNELS*8-1:0]sample[0:2];
 generate for(t=0;t<3;t=t+1)begin:gather
  assign sample[t]=!rd_sample_valid[t]?{CHANNELS*8{1'b0}}:rd_mask[t]?bank_data[rd_bank[t]]:partial[t];
  always @(posedge clk)if(step && rd_valid && !rd_complete && rd_mask[t])partial[t]<=bank_data[rd_bank[t]];
 end endgenerate
 wire mac_issue=rd_valid && rd_complete;
 reg[2:0]valid_pipe,first_pipe,last_pipe,inside_pipe;
 reg quant_valid,round_valid,quant_inside,round_inside;reg[31:0]emitted;
 wire[CHANNELS*9*8-1:0]weights;wire[CHANNELS*24-1:0]biases;wire[CHANNELS*5-1:0]shifts;
 full_shared_params #(.LAYER(LAYER),.NW(CHANNELS*9),.COUT(CHANNELS)) constants(.weights(weights),.biases(biases),.shifts(shifts));
 generate for(c=0;c<CHANNELS;c=c+1)begin:channel
  wire signed[17:0]product[0:2];
  for(t=0;t<3;t=t+1)begin:tap
   (* syn_use_dsp="yes" *)reg signed[17:0]p;
   wire signed[7:0]w=weights[(c*9+rd_row*3+t)*8+:8];
   always @(posedge clk)if(step && mac_issue)p<=$signed({1'b0,sample[t][c*8+:8]})*$signed(w);
   assign product[t]=p;
  end
  reg signed[23:0]pair,tail,dot,acc,completed;reg signed[24:0]rounded_sum;
  wire signed[23:0]bias=biases[c*24+:24];wire[4:0]shift=shifts[c*5+:5];
  wire signed[23:0]sum=(first_pipe[2]?bias:acc)+dot;
  wire signed[24:0]q=rounded_sum>>>shift;
  always @(posedge clk)begin
   if(step && valid_pipe[0])begin pair<=$signed(product[0])+$signed(product[1]);tail<=$signed(product[2]);end
   if(step && valid_pipe[1])dot<=pair+tail;
   if(step && valid_pipe[2])begin acc<=sum;if(last_pipe[2])completed<=sum;end
   if(step && quant_valid)rounded_sum<={{1{completed[23]}},completed}+(shift==0?25'sd0:(25'sd1<<(shift-1)));
   if(step && round_valid)out_data[c*8+:8]<=!round_inside || q<0?8'd0:q>255?8'd255:q[7:0];
   if(reset || start)acc<=0;
  end
 end endgenerate
 task automatic advance;
 begin
  if(px==PW-1)begin px<=0;row_ptr<=row_ptr==ROWS-1?0:row_ptr+1'b1;
   if(py==PH-1)state<=DRAIN;else begin py<=py+1;state<=FEED;end
  end else begin px<=px+1;state<=FEED;end
 end endtask
 integer j;
 always @(posedge clk)begin
  if(step)begin
   write_base<=scaled_row(row_ptr);
   if(state==FEED)begin row_bases[0]<=base_for(0);row_bases[1]<=base_for(1);row_bases[2]<=base_for(2);end
   mapped_inside<=predict_inside;mapped_px<=predict_px;
   first_enable<=nx_first_enable;second_enable<=nx_second_enable;first_mask<=nx_first_mask;second_mask<=nx_second_mask;
   sample_valid<=mapped_valid;sample_inside<=mapped_inside;sample_px<=mapped_px;need_second<=|nx_second_enable;
   for(j=0;j<3;j=j+1)begin first_column[j]<=nx_first_column[j];second_column[j]<=nx_second_column[j];sample_bank[j]<=nx_bank[j];end
   rd_valid<=state==READ;rd_complete<=!need_second || second_phase;rd_inside<=sample_inside;
   rd_row<=row_select;rd_mask<=request_mask;rd_sample_valid<=sample_valid;
   for(j=0;j<3;j=j+1)rd_bank[j]<=sample_bank[j];
   valid_pipe<={valid_pipe[1:0],mac_issue};first_pipe<={first_pipe[1:0],mac_issue && rd_row==0};
   last_pipe<={last_pipe[1:0],mac_issue && rd_row==2};inside_pipe<={inside_pipe[1:0],rd_inside};
   if(mac_issue && rd_row==1)center_store<=sample[1];
   quant_valid<=valid_pipe[2] && last_pipe[2];
   if(valid_pipe[2] && last_pipe[2])begin quant_inside<=inside_pipe[2];quant_center<=center_store;end
   round_valid<=quant_valid;if(quant_valid)begin round_inside<=quant_inside;round_center<=quant_center;end
   if(out_valid && out_ready)begin out_valid<=0;emitted<=emitted+1;if(emitted==WIDTH*HEIGHT-1)state<=IDLE;end
   if(round_valid)begin out_valid<=1;out_inside<=round_inside;out_center<=round_center;end
   case(state)
    FEED:if(!actual || in_valid)begin
     if(px>=2*DILATION && py>=2*DILATION)begin row_select<=0;second_phase<=0;state<=READ;end else advance();
    end
    READ:if(need_second && !second_phase)second_phase<=1;
     else begin second_phase<=0;if(row_select==2)advance();else row_select<=row_select+1'b1;end
    default:begin end
   endcase
  end
  if(reset || start)begin
   state<=reset?IDLE:FEED;px<=0;py<=0;row_ptr<=0;origin<=origin_x;row_select<=0;second_phase<=0;
   rd_valid<=0;rd_complete<=0;rd_inside<=0;rd_row<=0;rd_mask<=0;rd_sample_valid<=0;
   mapped_inside<=0;mapped_px<=0;sample_px<=0;first_enable<=0;second_enable<=0;first_mask<=0;second_mask<=0;sample_valid<=0;sample_inside<=0;need_second<=0;
   write_base<=0;row_bases[0]<=0;row_bases[1]<=0;row_bases[2]<=0;
   for(j=0;j<3;j=j+1)begin first_column[j]<=0;second_column[j]<=0;sample_bank[j]<=0;end
   valid_pipe<=0;first_pipe<=0;last_pipe<=0;inside_pipe<=0;quant_valid<=0;round_valid<=0;
   quant_inside<=0;round_inside<=0;out_valid<=0;out_inside<=0;out_center<=0;center_store<=0;quant_center<=0;round_center<=0;emitted<=0;
  end
 end
endmodule
