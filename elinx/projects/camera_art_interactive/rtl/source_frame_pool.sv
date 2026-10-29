// Three DDR source slots: one producer, latest complete, and a CNN-locked slot.
// Publication is supplied ONLY after frame validation and the final AXI B.
module source_frame_pool(input wire clk,reset,
 input wire allocate,output reg allocation_ack,output reg[1:0] capture_bank,
 input wire publish,abort_capture,input wire[31:0] capture_frame,
 input wire claim,release_source,output reg claim_ack,output reg[1:0] engine_bank,
 output reg[31:0] engine_frame,output reg latest_valid,output reg[31:0] latest_frame,
 output reg[31:0] captured_frames,skipped_frames,
 output wire capturing,locked);
 reg capture_owned,engine_owned;
 reg[1:0] latest_bank;
 reg[1:0] free_bank;
 reg free_found;
 integer i;
 assign capturing=capture_owned;assign locked=engine_owned;
 always @* begin
  free_found=0;free_bank=0;
  for(i=0;i<3;i=i+1)if(!free_found &&
    (!latest_valid || latest_bank!=i) && (!engine_owned || engine_bank!=i) &&
    (!capture_owned || capture_bank!=i))begin free_bank=i;free_found=1;end
 end
 always @(posedge clk)begin
  allocation_ack<=0;claim_ack<=0;
  if(reset)begin capture_owned<=0;engine_owned<=0;capture_bank<=0;engine_bank<=0;
   latest_bank<=0;latest_valid<=0;latest_frame<=0;engine_frame<=0;captured_frames<=0;skipped_frames<=0;end
  else begin
   if(release_source)engine_owned<=0;
   if(abort_capture)capture_owned<=0;
   if(allocate && !capture_owned && free_found)begin capture_bank<=free_bank;capture_owned<=1;allocation_ack<=1;end
   if(claim && !engine_owned && latest_valid)begin
    engine_owned<=1;engine_bank<=latest_bank;engine_frame<=latest_frame;latest_valid<=0;claim_ack<=1;
   end
   if(publish && capture_owned)begin
    // Claiming the previous latest on the same edge is allowed; the newly
    // published frame remains latest. Never overwrite the locked source.
    if(latest_valid && !(claim && !engine_owned))skipped_frames<=skipped_frames+1;
    latest_bank<=capture_bank;latest_frame<=capture_frame;latest_valid<=1;
    captured_frames<=captured_frames+1;capture_owned<=0;
   end
  end
 end
endmodule
