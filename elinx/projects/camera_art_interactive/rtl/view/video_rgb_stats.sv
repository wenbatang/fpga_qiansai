// UI-clock observation only. Sum expanded RGB565 channels, two pixels/beat.
// Publish only an exact, non-bad frame. No feedback to sensor or image path.
module video_rgb_stats #(parameter integer WIDTH=640,HEIGHT=480)(
 input wire clk,reset,frame_start,frame_end,frame_bad,pixel_valid,
 input wire[31:0] pixels,output reg[127:0] stats);
 reg active;reg[31:0] count,sr,sg,sb;
 wire[15:0] p=pixels[15:0],q=pixels[31:16];
 wire[7:0] pr={p[15:11],p[15:13]},pg={p[10:5],p[10:9]},pb={p[4:0],p[4:2]};
 wire[7:0] qr={q[15:11],q[15:13]},qg={q[10:5],q[10:9]},qb={q[4:0],q[4:2]};
 wire take=active && pixel_valid;
 wire[31:0] nc=count+(take ? 2:0);
 wire[31:0] nr=sr+(take ? {24'd0,pr}+{24'd0,qr}:0);
 wire[31:0] ng=sg+(take ? {24'd0,pg}+{24'd0,qg}:0);
 wire[31:0] nb=sb+(take ? {24'd0,pb}+{24'd0,qb}:0);
 always @(posedge clk)begin
  if(reset)begin active<=0;count<=0;sr<=0;sg<=0;sb<=0;stats<=0;end
  else if(frame_start)begin active<=1;count<=0;sr<=0;sg<=0;sb<=0;end
  else if(active)begin
   count<=nc;sr<=nr;sg<=ng;sb<=nb;
   if(frame_end)begin
    active<=0;
    if(!frame_bad && nc==WIDTH*HEIGHT)stats<={nc,nr,ng,nb};
   end
  end
 end
endmodule
