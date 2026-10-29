// Count NEW complete frames in one UI-clock second; HDMI repeats aren't inference.
// Bundle is stable from toggle request until pixel ACK. Apply in vblank only.
module fps_snapshot #(parameter CLOCK_HZ=100000000)(input wire clk,reset,
 input wire[31:0] captured,inferred,input wire pixel_clk,pixel_reset,vblank,
 output reg[7:0] capture_fps,inference_fps);
 reg[31:0] ticks,old_capture,old_inference;
 reg[15:0] bundle;
 reg request,ack;
 (* async_reg="true",syn_srlstyle="registers" *) reg[1:0] ack_sync,request_sync;
 wire[31:0] dc=captured-old_capture,di=inferred-old_inference;
 always @(posedge clk)begin
  if(reset)begin ticks<=0;old_capture<=0;old_inference<=0;bundle<=0;request<=0;ack_sync<=0;end
  else begin
   ack_sync<={ack_sync[0],ack};
   if(ticks==CLOCK_HZ-1)begin
    ticks<=0;old_capture<=captured;old_inference<=inferred;
    if(ack_sync[1]==request)begin
     bundle<={dc>99 ? 8'd99:dc[7:0],di>99 ? 8'd99:di[7:0]};request<=!request;
    end
   end else ticks<=ticks+1;
  end
 end
 always @(posedge pixel_clk)begin
  if(pixel_reset)begin request_sync<=0;ack<=0;capture_fps<=0;inference_fps<=0;end
  else begin
   request_sync<={request_sync[0],request};
   if(vblank && request_sync[1]!=ack)begin
    {capture_fps,inference_fps}<=bundle;ack<=request_sync[1];
   end
  end
 end
endmodule
