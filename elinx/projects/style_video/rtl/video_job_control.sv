// One job/one pending styled frame. Lock the source before launching CNN,
// release it only on done/error, and don't reuse the output until vblank ACK.
module video_job_control(input wire clk,reset,start,
 output wire busy,output wire claim,input wire claim_ack,input wire[31:0] source_frame,
 output reg release_source,engine_start,input wire engine_done,engine_error,
 output reg commit_valid,output reg commit_bank,output reg[31:0] commit_frame,
 input wire commit_ack,front_bank,front_valid,
 output reg completed,failed,output reg[31:0] inference_frames);
 localparam IDLE=0,CLAIM=1,RUN=2,COMMIT=3;
 reg[1:0] state;
 assign busy=state!=IDLE || start;
 assign claim=state==CLAIM;
 always @(posedge clk)begin
  release_source<=0;engine_start<=0;completed<=0;failed<=0;
  if(reset)begin state<=IDLE;commit_valid<=0;commit_bank<=0;commit_frame<=0;inference_frames<=0;end
  else case(state)
   IDLE:if(start)state<=CLAIM;
   CLAIM:if(claim_ack)begin
    commit_frame<=source_frame;commit_bank<=front_valid ? !front_bank:1'b0;
    engine_start<=1;state<=RUN;
   end
   RUN:begin
    if(engine_done)begin release_source<=1;commit_valid<=1;state<=COMMIT;inference_frames<=inference_frames+1;end
    else if(engine_error)begin release_source<=1;failed<=1;state<=IDLE;end
   end
   COMMIT:if(commit_ack)begin commit_valid<=0;completed<=1;state<=IDLE;end
   default:state<=IDLE;
  endcase
 end
endmodule
