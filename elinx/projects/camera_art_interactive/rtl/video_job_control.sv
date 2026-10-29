// Three output slots, two ordered complete-frame queue entries. A slot belongs
// to exactly one of FRONT, READY(head/tail), or the CLAIM/RUN job. Only a
// frame_reader_fps commit_ack (after old reads and FIFO reset have drained)
// retires the previous FRONT. Early reader.front_bank changes do not free it.
// engine_done is a contract: every output pixel AND the final AXI B succeeded.
// completed is a compute-complete IRQ, independently of displayed/commit_ack.
module video_job_control(
 input wire clk,reset,start,raw_mode,
 output wire busy,claim,input wire claim_ack,input wire[31:0]source_frame,
 output reg release_source,engine_start,input wire engine_done,engine_error,
 output reg[1:0]output_bank,
 output reg commit_valid,output reg[1:0]commit_bank,
 output reg[31:0]commit_frame,output reg commit_raw,
 input wire commit_ack,input wire[1:0]front_bank,input wire front_valid,
 output reg completed,failed,displayed,output reg[31:0]inference_frames
);
 localparam IDLE=0,CLAIM=1,RUN=2;
 reg[1:0]state,state_next;
 reg front_owned,front_owned_next;
 reg[1:0]front_owned_bank,front_owned_bank_next;
 reg tail_valid,tail_valid_next,tail_raw,tail_raw_next;
 reg[1:0]tail_bank,tail_bank_next;
 reg[31:0]tail_frame,tail_frame_next;
 reg[31:0]job_frame,job_frame_next;
 reg job_raw,job_raw_next;
 reg commit_valid_next,commit_raw_next;
 reg[1:0]commit_bank_next,output_bank_next;
 reg[31:0]commit_frame_next,inference_frames_next;
 reg release_source_next,engine_start_next,completed_next,failed_next,displayed_next;
 reg free_found;reg[1:0]free_bank;integer i;

 // front_bank/front_valid are reader observations only. The reader may expose
 // its new front before it acknowledges the FIFO drain. The authoritative
 // reservation is front_owned_bank, advanced only by the ACK below.
 always @*begin
  free_found=0;free_bank=0;
  for(i=0;i<3;i=i+1)if(!free_found &&
   (!front_owned || front_owned_bank!=i) &&
   (!commit_valid || commit_bank!=i) &&
   (!tail_valid || tail_bank!=i) &&
   (state==IDLE || output_bank!=i))begin free_found=1;free_bank=i;end
 end
 // A two-entry completed queue also bounds startup when no FRONT exists.
 // Even if a third slot is free, do not launch into a full completed queue.
 wire can_start=state==IDLE && free_found && !tail_valid;
 assign busy=!can_start || start;
 assign claim=state==CLAIM;

 always @*begin
  state_next=state;front_owned_next=front_owned;front_owned_bank_next=front_owned_bank;
  tail_valid_next=tail_valid;tail_raw_next=tail_raw;tail_bank_next=tail_bank;tail_frame_next=tail_frame;
  job_frame_next=job_frame;job_raw_next=job_raw;
  commit_valid_next=commit_valid;commit_raw_next=commit_raw;commit_bank_next=commit_bank;commit_frame_next=commit_frame;
  output_bank_next=output_bank;inference_frames_next=inference_frames;
  release_source_next=0;engine_start_next=0;completed_next=0;failed_next=0;displayed_next=0;

  // Pop first, then enqueue a simultaneous engine completion. This preserves
  // completion order and never presents a different payload before its ACK.
  if(commit_valid && commit_ack)begin
   front_owned_next=1;front_owned_bank_next=commit_bank;displayed_next=1;
   commit_valid_next=tail_valid;
   if(tail_valid)begin commit_bank_next=tail_bank;commit_frame_next=tail_frame;commit_raw_next=tail_raw;end
   tail_valid_next=0;
  end

  case(state)
   IDLE:if(start && can_start)begin output_bank_next=free_bank;state_next=CLAIM;end
   CLAIM:if(claim_ack)begin job_frame_next=source_frame;engine_start_next=1;state_next=RUN;end
   RUN:begin
    // engine_start is a registered pulse. Capture raw_mode at the edge at
    // which the engine actually samples that pulse, rather than at START.
    if(engine_start)job_raw_next=raw_mode;
    if(engine_error)begin
     // Error wins if an invalid engine asserts done/error together.
     release_source_next=1;failed_next=1;state_next=IDLE;
    end else if(engine_done)begin
     release_source_next=1;completed_next=1;state_next=IDLE;
     inference_frames_next=inference_frames+1'b1;
     if(!commit_valid_next)begin
      commit_valid_next=1;commit_bank_next=output_bank;commit_frame_next=job_frame;
      commit_raw_next=engine_start ? raw_mode:job_raw;
     end else begin
      // At most one queue entry was present when this job was admitted;
      // only ACK can remove entries while it runs, so the tail is free.
      tail_valid_next=1;tail_bank_next=output_bank;tail_frame_next=job_frame;
      tail_raw_next=engine_start ? raw_mode:job_raw;
     end
    end
   end
   default:state_next=IDLE;
  endcase
 end

 always @(posedge clk)begin
  if(reset)begin
   state<=IDLE;front_owned<=0;front_owned_bank<=0;tail_valid<=0;tail_raw<=0;tail_bank<=0;tail_frame<=0;
   job_frame<=0;job_raw<=0;output_bank<=0;commit_valid<=0;commit_bank<=0;commit_frame<=0;commit_raw<=0;
   release_source<=0;engine_start<=0;completed<=0;failed<=0;displayed<=0;inference_frames<=0;
  end else begin
   state<=state_next;front_owned<=front_owned_next;front_owned_bank<=front_owned_bank_next;
   tail_valid<=tail_valid_next;tail_raw<=tail_raw_next;tail_bank<=tail_bank_next;tail_frame<=tail_frame_next;
   job_frame<=job_frame_next;job_raw<=job_raw_next;output_bank<=output_bank_next;
   commit_valid<=commit_valid_next;commit_bank<=commit_bank_next;commit_frame<=commit_frame_next;commit_raw<=commit_raw_next;
   release_source<=release_source_next;engine_start<=engine_start_next;completed<=completed_next;failed<=failed_next;
   displayed<=displayed_next;inference_frames<=inference_frames_next;
  end
 end
endmodule
