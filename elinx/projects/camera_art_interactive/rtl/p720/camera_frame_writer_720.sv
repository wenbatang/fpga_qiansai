// Consume camera FIFO continuously; DDR errors/gaps discard the entire frame.
// No publication until the EOF record, exact word count, and final B response.
module camera_frame_writer_720 #(parameter WIDTH=640,HEIGHT=480,
 parameter[29:0] SOURCE_BASE=30'h00400000,BANK_STRIDE=30'h00200000)(
 input wire clk,reset,input wire[178:0] fifo_data,input wire fifo_empty,output wire fifo_read,
 output reg allocate,input wire allocation_ack,input wire[1:0] capture_bank,
 output reg publish,abort_capture,output reg[31:0] capture_frame,error_frames,
 output reg[29:0] awaddr,output wire awvalid,input wire awready,
 output reg[127:0] wdata,output wire wvalid,input wire wready,
 input wire[1:0] bresp,input wire bvalid,output wire bready);
 localparam IDLE=0,ALLOCATE=1,ALLOC_WAIT=2,WRITE=3,RESP=4;
 reg[2:0] state;reg active,bad,aw_done,w_done;
 reg[16:0] expected;reg[1:0] bank;
 wire eof=fifo_data[178],record_bad=fifo_data[177];
 wire[31:0] fid=fifo_data[176:145];wire[16:0] index=fifo_data[144:128];
 wire first=!eof && index==0;
 wire new_frame=first && (!active || fid!=capture_frame);
 assign fifo_read=state==IDLE && !fifo_empty && !new_frame;
 assign awvalid=state==WRITE && !aw_done;
 assign wvalid=state==WRITE && !w_done;
 assign bready=state==RESP;
 always @(posedge clk)begin
  allocate<=0;publish<=0;abort_capture<=0;
  if(reset)begin state<=IDLE;active<=0;bad<=0;aw_done<=0;w_done<=0;expected<=0;bank<=0;
   awaddr<=0;wdata<=0;capture_frame<=0;error_frames<=0;end
  else case(state)
   IDLE:if(!fifo_empty)begin
    if(new_frame)begin
     if(active)begin abort_capture<=1;error_frames<=error_frames+1;end
     active<=0;state<=ALLOCATE;
    end else if(fifo_read)begin
     if(active && fid==capture_frame)begin
      if(eof)begin
       if(!bad && !record_bad && expected==WIDTH*HEIGHT/8 && index==expected)publish<=1;
       else begin abort_capture<=1;error_frames<=error_frames+1;end
       active<=0;
      end else if(!bad)begin
       if(record_bad || index!=expected || expected>=WIDTH*HEIGHT/8)bad<=1;
       else begin
        awaddr<=SOURCE_BASE+bank*BANK_STRIDE+{9'd0,expected,4'd0};wdata<=fifo_data[127:0];
        expected<=expected+1;aw_done<=0;w_done<=0;state<=WRITE;
       end
      end
     end
    end
   end
   ALLOCATE:begin allocate<=1;state<=ALLOC_WAIT;end
   ALLOC_WAIT:if(allocation_ack)begin
    bank<=capture_bank;capture_frame<=fid;expected<=0;bad<=0;active<=1;state<=IDLE;
   end
   WRITE:begin
    if(awvalid && awready)aw_done<=1;
    if(wvalid && wready)w_done<=1;
    if((aw_done || awready) && (w_done || wready))state<=RESP;
   end
   RESP:if(bvalid)begin if(bresp!=0)bad<=1;state<=IDLE;end
   default:state<=IDLE;
  endcase
 end
endmodule
