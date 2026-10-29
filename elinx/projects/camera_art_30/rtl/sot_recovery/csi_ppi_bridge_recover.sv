// D-PHY PPI -> atomic asynchronous FIFO -> CSI RAW10 decoding in UI domain.
// VC0, four lanes, fixed RAW_WIDTH, one CSI packet per HS transmission.
// Rejects header ECC errors (including correctable single-bit errors), CRC
// errors, unexpected size/format and interrupted packets. No raw metadata bus
// crosses domains outside the FIFO. HS trailing bytes are discarded until SoT.
module csi_ppi_bridge_recover #(
 parameter integer RAW_WIDTH=1920,RAW_HEIGHT=1080,FRAME_TIMEOUT=5000000
)(input wire byte_clk,byte_reset,ui_clk,ui_reset,
 input wire[31:0] ppi_data,input wire[3:0] ppi_valid,ppi_sync,ppi_sot_error,
 input wire control_error,
 output reg vs,hs,valid,output reg[39:0] raw,
 output wire packet_error,output reg[31:0] good_lines,error_packets,
 output wire transport_fault,
// TRACE_PORT_BEGIN
 output reg[31:0] debug_events,debug_header,
 output wire[383:0] trace_fields
// RECOVERY_PORT_BEGIN
 ,output reg[31:0] soft_sot_records
// RECOVERY_PORT_END
);
// TRACE_PORT_END
 localparam integer LINE_BYTES=RAW_WIDTH*10/8;
 wire fifo_full,fifo_empty;wire[43:0] fifo_data;
 wire write_event=|ppi_valid || |ppi_sync || |ppi_sot_error;
 reg overflow_byte=0;
 always @(posedge byte_clk or posedge ui_reset)
  if(ui_reset)overflow_byte<=0;
  else if(!byte_reset && write_event && fifo_full)overflow_byte<=1;
 (* async_reg="true",syn_srlstyle="registers" *) reg[1:0] overflow_sync=0;
 always @(posedge ui_clk or posedge ui_reset)
  if(ui_reset)overflow_sync<=0;else overflow_sync<={overflow_sync[0],overflow_byte};
 assign transport_fault=overflow_sync[1];
 efx_fifo_wrapper #(.FAMILY("TITANIUM"),.SYNC_CLK(0),.SYNC_STAGE(2),.BYPASS_RESET_SYNC(0),
  .MODE("FWFT"),.DEPTH(512),.DATA_WIDTH(44),.PIPELINE_REG(1),.OUTPUT_REG(0)) ppi_fifo(
  .a_rst_i(ui_reset),.a_wr_rst_i(1'b0),.a_rd_rst_i(1'b0),.clk_i(1'b0),.wr_clk_i(byte_clk),.rd_clk_i(ui_clk),
  .wr_en_i(!byte_reset && write_event && !fifo_full),.rd_en_i(!fifo_empty),
  .wdata({ppi_sot_error,ppi_sync,ppi_valid,ppi_data}),.rdata(fifo_data),
  .full_o(fifo_full),.empty_o(fifo_empty),.almost_full_o(),.prog_full_o(),.overflow_o(),
  .wr_ack_o(),.datacount_o(),.almost_empty_o(),.prog_empty_o(),.underflow_o(),.rd_valid_o(),
  .rd_datacount_o(),.wr_datacount_o(),.rst_busy());
 wire[3:0] in_valid=fifo_empty?4'd0:fifo_data[35:32];
 wire[3:0] in_sync=fifo_empty?4'd0:fifo_data[39:36];
 wire in_error=!fifo_empty && |fifo_data[43:40];
 (* syn_ramstyle="registers" *) reg[7:0] lanes[0:63];
 reg[3:0] wp[0:3],rp[0:3];reg[4:0] count[0:3];
 reg[3:0] armed,sync_seen;
 wire all_bytes=(count[0]!=0 && count[1]!=0 && count[2]!=0 && count[3]!=0);
 wire crc_bytes=(count[0]!=0 && count[1]!=0);
 wire[31:0] word_data={lanes[48+rp[3]],lanes[32+rp[2]],lanes[16+rp[1]],lanes[rp[0]]};
 localparam WAIT_SOT=0,HEADER=1,PAYLOAD=2,CRC=3;
 reg[1:0] state;
// RECOVERY_CLASSIFIER_BEGIN
 // A SoT status record alone may be tolerated only between fully drained packets.
 // This does not publish a frame: normal FS/FE, line count, header ECC, CRC,
 // RAW dimensions, timeout, lane queues and transport checks still all apply.
 wire soft_sot_error=in_error && state==WAIT_SOT && sync_seen==0 &&
  count[0]==0 && count[1]==0 && count[2]==0 && count[3]==0 &&
  in_valid==0 && in_sync==0;
 wire hard_sot_error=in_error && !soft_sot_error;
 always @(posedge ui_clk)begin
  if(ui_reset)soft_sot_records<=0;
  else if(soft_sot_error)soft_sot_records<=soft_sot_records+1;
 end
// RECOVERY_CLASSIFIER_END
 reg[15:0] remaining,crc_value,line_count;
 reg[63:0] raw_buffer;reg[3:0] raw_bytes;
 reg bad,fs_pending;reg[22:0] frame_ticks;
 wire[3:0] pop=(|in_sync)?4'd0:
  ((state==HEADER || state==PAYLOAD)?(all_bytes?4'hf:4'd0):
   (state==CRC?(crc_bytes?4'h3:4'd0):(sync_seen!=0?4'd0:{count[3]!=0,count[2]!=0,count[1]!=0,count[0]!=0})));
 wire[3:0] push=in_valid & armed & ~in_sync;
 wire lane_overflow=|(push & {count[3]==16,count[2]==16,count[1]==16,count[0]==16} & ~pop);
 assign packet_error=bad || transport_fault;
 function automatic[5:0] header_ecc(input[23:0] d);
  begin
   header_ecc[0]=d[0]^d[1]^d[2]^d[4]^d[5]^d[7]^d[10]^d[11]^d[13]^d[16]^d[20]^d[21]^d[22]^d[23];
   header_ecc[1]=d[0]^d[1]^d[3]^d[4]^d[6]^d[8]^d[10]^d[12]^d[14]^d[17]^d[20]^d[21]^d[22]^d[23];
   header_ecc[2]=d[0]^d[2]^d[3]^d[5]^d[6]^d[9]^d[11]^d[12]^d[15]^d[18]^d[20]^d[21]^d[22];
   header_ecc[3]=d[1]^d[2]^d[3]^d[7]^d[8]^d[9]^d[13]^d[14]^d[15]^d[19]^d[20]^d[21]^d[23];
   header_ecc[4]=d[4]^d[5]^d[6]^d[7]^d[8]^d[9]^d[16]^d[17]^d[18]^d[19]^d[20]^d[22]^d[23];
   header_ecc[5]=d[10]^d[11]^d[12]^d[13]^d[14]^d[15]^d[16]^d[17]^d[18]^d[19]^d[21]^d[22]^d[23];
  end
 endfunction
 function automatic[15:0] crc32(input[15:0] initial_crc,input[31:0] data);
  reg[15:0] c;integer bit_index;
  begin c=initial_crc;for(bit_index=0;bit_index<32;bit_index=bit_index+1)
   if(c[0]^data[bit_index])c=(c>>1)^16'h8408;else c=c>>1;
   crc32=c;
  end
 endfunction
 wire[63:0] assembled=raw_buffer | ({32'd0,word_data} << (raw_bytes*8));
 wire[3:0] assembled_bytes=raw_bytes+4;
 integer lane;
 always @(posedge ui_clk)begin
  valid<=0;
  if(ui_reset)begin
   vs<=0;hs<=0;raw<=0;state<=WAIT_SOT;armed<=0;sync_seen<=0;
   remaining<=0;crc_value<=16'hffff;raw_buffer<=0;raw_bytes<=0;
   bad<=0;fs_pending<=0;frame_ticks<=0;line_count<=0;good_lines<=0;error_packets<=0;
   for(lane=0;lane<4;lane=lane+1)begin wp[lane]<=0;rp[lane]<=0;count[lane]<=0;end
  end else begin
   for(lane=0;lane<4;lane=lane+1)begin
    if(in_sync[lane])begin
     wp[lane]<=0;rp[lane]<=0;count[lane]<=0;armed[lane]<=1;
    end else begin
     if(push[lane] && (count[lane]<16 || pop[lane]))begin
      lanes[lane*16+wp[lane]]<=fifo_data[lane*8+:8];wp[lane]<=wp[lane]+1;
     end
     if(pop[lane])rp[lane]<=rp[lane]+1;
     case({push[lane] && (count[lane]<16 || pop[lane]),pop[lane]})
      2'b10:count[lane]<=count[lane]+1;
      2'b01:count[lane]<=count[lane]-1;
     endcase
    end
   end
   if(vs)frame_ticks<=frame_ticks+1;else frame_ticks<=0;
   if(fs_pending)begin vs<=1;bad<=0;line_count<=0;frame_ticks<=0;fs_pending<=0;end
   if(control_error || hard_sot_error || lane_overflow || transport_fault)begin
    bad<=1;error_packets<=error_packets+1;hs<=0;state<=WAIT_SOT;
   end else if(|in_sync)begin
    if(state==PAYLOAD || state==CRC || state==HEADER)begin bad<=1;error_packets<=error_packets+1;end
    hs<=0;raw_buffer<=0;raw_bytes<=0;
    if(in_sync==4'hf)begin state<=HEADER;sync_seen<=0;end
    else if((sync_seen & in_sync)!=0)begin sync_seen<=in_sync;state<=WAIT_SOT;bad<=1;end
    else if((sync_seen | in_sync)==4'hf)begin state<=HEADER;sync_seen<=0;end
    else begin sync_seen<=sync_seen | in_sync;state<=WAIT_SOT;end
   end else case(state)
    HEADER:if(all_bytes)begin
     state<=WAIT_SOT;
     if(word_data[31:30]!=0 || word_data[29:24]!=header_ecc(word_data[23:0]) || word_data[7:6]!=0)begin
      bad<=1;error_packets<=error_packets+1;
     end else case(word_data[5:0])
      6'h00:begin
       if(vs)begin vs<=0;bad<=1;fs_pending<=1;end
       else begin vs<=1;bad<=0;line_count<=0;frame_ticks<=0;end
      end
      6'h01:begin
       if(!vs || line_count!=RAW_HEIGHT)begin bad<=1;error_packets<=error_packets+1;end
       vs<=0;hs<=0;
      end
      6'h02,6'h03:begin end // Optional LS/LE; RAW packet boundaries determine HS.
      6'h2b:begin
       if(vs && word_data[23:8]==LINE_BYTES && line_count<RAW_HEIGHT)begin
        state<=PAYLOAD;remaining<=LINE_BYTES;crc_value<=16'hffff;raw_buffer<=0;raw_bytes<=0;hs<=1;
       end else begin bad<=1;error_packets<=error_packets+1;end
      end
      default:begin bad<=1;error_packets<=error_packets+1;end
     endcase
    end
    PAYLOAD:if(all_bytes)begin
     crc_value<=crc32(crc_value,word_data);remaining<=remaining-4;
     if(assembled_bytes>=5)begin
      raw<={{assembled[31:24],assembled[39:38]},{assembled[23:16],assembled[37:36]},
            {assembled[15:8],assembled[35:34]},{assembled[7:0],assembled[33:32]}};
      valid<=1;raw_buffer<=assembled>>40;raw_bytes<=assembled_bytes-5;
     end else begin raw_buffer<=assembled;raw_bytes<=assembled_bytes;end
     if(remaining==4)state<=CRC;
    end
    CRC:if(crc_bytes)begin
     if(word_data[15:0]!=crc_value || raw_bytes!=0)begin bad<=1;error_packets<=error_packets+1;end
     else begin good_lines<=good_lines+1;line_count<=line_count+1;end
     hs<=0;state<=WAIT_SOT;
    end
   endcase
   if(vs && frame_ticks==FRAME_TIMEOUT-1)begin
    vs<=0;hs<=0;bad<=1;state<=WAIT_SOT;fs_pending<=0;error_packets<=error_packets+1;
   end
  end
 end
always @(posedge ui_clk)begin
  if(ui_reset)begin debug_events<=0;debug_header<=0;end
  else begin
   if(!fifo_empty)debug_events<=debug_events+1;
   if(state==HEADER && all_bytes && !control_error && !in_error &&
      !lane_overflow && !transport_fault && !(|in_sync))debug_header<=word_data;
  end
 end
// TRACE_OBSERVER_BEGIN
 // Observations only: no original signal, ready, error, or state is driven here.
 // Raw control/SoT/lane events count even if another primary cause coincides.
 // Parser counters only count the branch actually selected by the original
 // priority chain. Timeout remains independent, as in the parser's last if.
 reg[31:0] trace_control_cycles,trace_control_rises,trace_sot_records;
 reg[31:0] trace_lane_overflows,trace_header_errors,trace_format_errors;
 reg[31:0] trace_crc_errors,trace_packet_interrupts,trace_fe_errors;
 reg[31:0] trace_timeout_errors,trace_fs_overlaps,trace_first_error_context;
 reg trace_control_previous;
 wire trace_primary_error=control_error || hard_sot_error || lane_overflow || transport_fault;
 wire trace_parser_cycle=!trace_primary_error && !(|in_sync);
 wire trace_header_cycle=trace_parser_cycle && state==HEADER && all_bytes;
 wire trace_header_bad=word_data[31:30]!=0 ||
      word_data[29:24]!=header_ecc(word_data[23:0]) || word_data[7:6]!=0;
 wire trace_header_valid=trace_header_cycle && !trace_header_bad;
 wire trace_raw_bad=word_data[5:0]==6'h2b &&
      !(vs && word_data[23:8]==LINE_BYTES && line_count<RAW_HEIGHT);
 wire trace_unknown_type=word_data[5:0]!=6'h00 && word_data[5:0]!=6'h01 &&
      word_data[5:0]!=6'h02 && word_data[5:0]!=6'h03 && word_data[5:0]!=6'h2b;
 wire trace_crc_bad=trace_parser_cycle && state==CRC && crc_bytes &&
      (word_data[15:0]!=crc_value || raw_bytes!=0);
 wire trace_interrupt=!trace_primary_error && (|in_sync) &&
      (state==PAYLOAD || state==CRC || state==HEADER);
 wire trace_partial_duplicate=!trace_primary_error && (|in_sync) &&
      in_sync!=4'hf && ((sync_seen & in_sync)!=0);
 wire trace_fe_bad=trace_header_valid && word_data[5:0]==6'h01 &&
      (!vs || line_count!=RAW_HEIGHT);
 wire trace_timeout=vs && frame_ticks==FRAME_TIMEOUT-1;
 wire trace_fs_overlap=trace_header_valid && word_data[5:0]==6'h00 && vs;
 // Mirror the old always block's effective error priority, including its
 // later partial-SoT assignment and final independent timeout assignment.
 reg[3:0] trace_reason;
 always @* begin
  trace_reason=0;
  if(trace_primary_error)begin
   if(control_error)trace_reason=1;
   else if(hard_sot_error)trace_reason=2;
   else if(lane_overflow)trace_reason=3;
   else trace_reason=4;
  end else if(|in_sync)begin
   if(trace_interrupt)trace_reason=8;
   if(trace_partial_duplicate)trace_reason=11;
  end else if(trace_header_cycle)begin
   if(trace_header_bad)trace_reason=5;
   else if(trace_raw_bad || trace_unknown_type)trace_reason=6;
   else if(trace_fe_bad)trace_reason=9;
   else if(trace_fs_overlap)trace_reason=12;
  end else if(trace_crc_bad)trace_reason=7;
  if(trace_timeout)trace_reason=10;
 end
 assign trace_fields={trace_control_cycles,trace_control_rises,trace_sot_records,
  trace_lane_overflows,trace_header_errors,trace_format_errors,trace_crc_errors,
  trace_packet_interrupts,trace_fe_errors,trace_timeout_errors,trace_fs_overlaps,
  trace_first_error_context};
 always @(posedge ui_clk)begin
  if(ui_reset)begin
   trace_control_cycles<=0;trace_control_rises<=0;trace_sot_records<=0;
   trace_lane_overflows<=0;trace_header_errors<=0;trace_format_errors<=0;
   trace_crc_errors<=0;trace_packet_interrupts<=0;trace_fe_errors<=0;
   trace_timeout_errors<=0;trace_fs_overlaps<=0;trace_first_error_context<=0;
   trace_control_previous<=0;
  end else begin
   trace_control_previous<=control_error;
   if(control_error)trace_control_cycles<=trace_control_cycles+1;
   if(control_error && !trace_control_previous)trace_control_rises<=trace_control_rises+1;
   if(in_error)trace_sot_records<=trace_sot_records+1;
   if(lane_overflow)trace_lane_overflows<=trace_lane_overflows+1;
   if(trace_header_cycle && trace_header_bad)trace_header_errors<=trace_header_errors+1;
   if(trace_header_valid && (trace_raw_bad || trace_unknown_type))trace_format_errors<=trace_format_errors+1;
   if(trace_crc_bad)trace_crc_errors<=trace_crc_errors+1;
   if(trace_interrupt)trace_packet_interrupts<=trace_packet_interrupts+1;
   if(trace_fe_bad)trace_fe_errors<=trace_fe_errors+1;
   if(trace_timeout)trace_timeout_errors<=trace_timeout_errors+1;
   if(trace_fs_overlap)trace_fs_overlaps<=trace_fs_overlaps+1;
   // Retain context at FS; update on each subsequent bad 0->1 transition.
   // This is the first fault in that bad episode, not just the first since boot.
   if(!bad && trace_reason!=0)trace_first_error_context<=
       {trace_reason,state,vs,hs,line_count,raw_bytes,sync_seen};
  end
 end
// TRACE_OBSERVER_END
endmodule
