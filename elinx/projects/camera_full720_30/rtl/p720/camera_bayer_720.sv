// Full RAW raster -> bilinear Bayer RGB at source positions floor(3*out/2).
// This preserves samples across the full 1920x1080 field, producing true
// 1280x720 processing input. No enlargement of the old 960x540 reduction.
// A UI-clock FIFO absorbs PPI bursts. Each four-pixel record takes two clocks.
// Two 16-bit line memories and three pairs of horizontal history form 3x3
// windows. Selected last coordinates are W-2/H-2, so no synthetic last row
// or column is needed. Left/top borders use reflect101.
module camera_bayer_720 #(
 parameter RAW_WIDTH=1920,RAW_HEIGHT=1080,WIDTH=RAW_WIDTH*2/3,HEIGHT=RAW_HEIGHT*2/3,
 parameter FIFO_DEPTH=512
)(input wire clk,reset,vs,hs,valid,input wire[39:0]raw,input wire[1:0]pattern,
 input wire packet_error,output reg[31:0]pixels,output reg pixel_valid,
 output reg frame_start,frame_end,frame_bad,output reg overflow);
 localparam integer PAIRS=RAW_WIDTH/2,AB=$clog2(PAIRS);
 reg vs_in,hs_in,err_in;
 wire event_in=valid || vs!=vs_in || hs!=hs_in || packet_error!=err_in;
 wire[43:0]record_in={vs,hs,valid,packet_error,raw};
 wire[43:0]record_out;wire full,empty,read_record;
 wire qvs=record_out[43],qhs=record_out[42],qvalid=record_out[41],qerror=record_out[40];
 wire[15:0]lo_pair={record_out[19:12],record_out[9:2]};
 wire[15:0]hi_pair={record_out[39:32],record_out[29:22]};
 efx_fifo_wrapper #(.FAMILY("TITANIUM"),.SYNC_CLK(1),.MODE("FWFT"),
  .DEPTH(FIFO_DEPTH),.DATA_WIDTH(44),.PIPELINE_REG(1),.OUTPUT_REG(0)) raw_queue(
  .a_rst_i(reset),.a_wr_rst_i(1'b0),.a_rd_rst_i(1'b0),.clk_i(clk),.wr_clk_i(1'b0),.rd_clk_i(1'b0),
  .wr_en_i(event_in && !full),.rd_en_i(read_record),.wdata(record_in),.rdata(record_out),
  .full_o(full),.empty_o(empty),.almost_full_o(),.prog_full_o(),.overflow_o(),.wr_ack_o(),.datacount_o(),
  .almost_empty_o(),.prog_empty_o(),.underflow_o(),.rd_valid_o(),.rd_datacount_o(),.wr_datacount_o(),.rst_busy());
 always @(posedge clk)begin
  if(reset)begin vs_in<=0;hs_in<=0;err_in<=0;overflow<=0;end
  else begin
   vs_in<=vs;hs_in<=hs;err_in<=packet_error;
   if(event_in && full)overflow<=1; // sticky, requires global reset
  end
 end
 localparam WAIT_RECORD=0,SECOND_PAIR=1,FINISH=2;
 reg[1:0]state;reg qvs_d,qhs_d,active,bad;reg[1:0]phase;
 reg[15:0]x,y,saved_hi;reg[2:0]flush_count;
 wire begin_event=read_record && !qvs_d && qvs;
 wire end_event=read_record && qvs_d && !qvs;
 wire line_end=read_record && qhs_d && !qhs;
 assign read_record=state==WAIT_RECORD && !empty;
 wire take0=read_record && qvalid && qhs && qvs && active;
 wire take1=state==SECOND_PAIR && active;
 wire take_pair=(take0 || take1) && x<RAW_WIDTH && y<RAW_HEIGHT;
 wire[15:0]pair_data=take1?saved_hi:lo_pair;
 (* ram_style="block" *)reg[15:0]row1[0:PAIRS-1],row2[0:PAIRS-1];
 reg[15:0]r1,r2,bottom;reg[AB-1:0]s_addr;reg[15:0]sx,sy;reg s_valid;
 // Delay the second-line write to use a synchronous first-line read.
 always @(posedge clk)begin
  if(take_pair)begin
   r1<=row1[x/2];r2<=row2[x/2];row1[x/2]<=pair_data;
  end
  if(s_valid)row2[s_addr]<=r1;
 end
 reg[15:0]left_top,left_mid,left_bot;
 wire[15:0]top=sy==1?bottom:r2;
 wire[15:0]mid=r1,bot=bottom;
 // Window A centered at sx-1; B centered at sx.
 wire[7:0]ta=left_top[7:0],tb=left_top[15:8],tc=top[7:0],td=top[15:8];
 wire[7:0]ma=left_mid[7:0],mb=left_mid[15:8],mc=mid[7:0],md=mid[15:8];
 wire[7:0]ba=left_bot[7:0],bb=left_bot[15:8],bc=bot[7:0],bd=bot[15:8];
 function automatic[7:0] avg2(input[7:0]a,b);
  reg[8:0]sum;begin sum={1'b0,a}+{1'b0,b}+1;avg2=sum[8:1];end
 endfunction
 function automatic[7:0] avg4(input[7:0]a,b,c,d);
  reg[9:0]sum;begin sum={2'b0,a}+{2'b0,b}+{2'b0,c}+{2'b0,d}+2;avg4=sum[9:2];end
 endfunction
 function automatic[15:0] color(input[7:0]nw,n,ne,w,c,e,sw,s,se,input[1:0]parity,bayer);
  reg[7:0]r,g,b;reg[1:0]pos;
  begin
   // pos0 blue, pos3 red, pos1/2 green for BGGR.
   pos=parity ^ (bayer==1?2'b11:bayer==2?2'b01:bayer==3?2'b10:2'b00);
   case(pos)
    0:begin b=c;r=avg4(nw,ne,sw,se);g=avg4(n,w,e,s);end
    3:begin r=c;b=avg4(nw,ne,sw,se);g=avg4(n,w,e,s);end
    1:begin g=c;b=avg2(w,e);r=avg2(n,s);end
    default:begin g=c;r=avg2(w,e);b=avg2(n,s);end
   endcase
   color={r[7:3],g[7:2],b[7:3]};
  end
 endfunction
 wire[15:0]ca=color(ta,tb,tc,ma,mb,mc,ba,bb,bc,{~sy[0],1'b1},phase);
 wire[15:0]cb=color(sx==0?td:tb,tc,td,sx==0?md:mb,mc,md,sx==0?bd:bb,bc,bd,{~sy[0],1'b0},phase);
 wire select_y=sy>0 && ((sy-1)%3)!=2;
 wire select_a=s_valid && select_y && sx>0 && ((sx-1)%3)!=2;
 wire select_b=s_valid && select_y && (sx%3)!=2;
 reg pending;reg[15:0]held;reg[31:0]output_count;
 always @(posedge clk)begin
  pixel_valid<=0;frame_start<=0;frame_end<=0;
  if(reset)begin
   state<=WAIT_RECORD;qvs_d<=0;qhs_d<=0;active<=0;bad<=0;phase<=0;x<=0;y<=0;saved_hi<=0;
   flush_count<=0;frame_bad<=0;s_valid<=0;s_addr<=0;sx<=0;sy<=0;bottom<=0;
   left_top<=0;left_mid<=0;left_bot<=0;pending<=0;held<=0;pixels<=0;output_count<=0;
  end else begin
   s_valid<=take_pair;
   if(take_pair)begin sx<=x;sy<=y;bottom<=pair_data;s_addr<=x/2;x<=x+2;end
   if(s_valid)begin left_top<=top;left_mid<=mid;left_bot<=bot;end
   if(select_a && select_b)begin
    pixel_valid<=1;output_count<=output_count+2;
    if(pending)begin pixels<={ca,held};held<=cb;end
    else begin pixels<={cb,ca};pending<=0;end
   end else if(select_a || select_b)begin
    if(pending)begin pixels<={select_a?ca:cb,held};pixel_valid<=1;output_count<=output_count+2;pending<=0;end
    else begin held<=select_a?ca:cb;pending<=1;end
   end
   if(read_record)begin
    qvs_d<=qvs;qhs_d<=qhs;
    if(begin_event)begin active<=1;bad<=qerror || overflow;x<=0;y<=0;phase<=pattern;
     frame_start<=1;frame_bad<=0;pending<=0;output_count<=0;end
    if(active && (qerror || overflow))bad<=1;
    if(line_end && active)begin if(x!=RAW_WIDTH)bad<=1;x<=0;y<=y+1;end
    if(qvalid)begin
     if(!active || !qvs || !qhs || x>=RAW_WIDTH || y>=RAW_HEIGHT)bad<=1;
     else begin saved_hi<=hi_pair;state<=SECOND_PAIR;end
    end
    if(end_event && active)begin
     if(y+(line_end?1:0)!=RAW_HEIGHT || (line_end && x!=RAW_WIDTH))bad<=1;
     active<=0;state<=FINISH;flush_count<=0;
    end
   end
   if(state==SECOND_PAIR)state<=WAIT_RECORD;
   if(state==FINISH)begin
    if(flush_count==3)begin
     frame_end<=1;frame_bad<=bad || overflow || pending || output_count!=WIDTH*HEIGHT;
     state<=WAIT_RECORD;
    end else flush_count<=flush_count+1'b1;
   end
  end
 end
endmodule
