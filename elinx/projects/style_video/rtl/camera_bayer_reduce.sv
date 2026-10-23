// V7 CSI output: four RAW10 pixels in bits [39:0], earliest in [9:0].
// A 2x2 Bayer block becomes one RGB pixel (two per beat), then a centered
// 640x480 crop from 960x540. This is explicit spatial reduction, not full ISP.
// pattern: 0 BGGR, 1 RGGB, 2 GBRG, 3 GRBG; must check a real color chart.
module camera_bayer_reduce #(
 parameter RAW_WIDTH=1920,RAW_HEIGHT=1080,WIDTH=640,HEIGHT=480
)(input wire clk,reset,vs,hs,valid,input wire[39:0] raw,input wire[1:0] pattern,
 input wire packet_error,
 output reg[31:0] pixels,output reg pixel_valid,frame_start,frame_end,frame_bad);
 localparam integer GROUPS=RAW_WIDTH/4;
 localparam integer CROP_X=(RAW_WIDTH/2-WIDTH)/2,CROP_Y=(RAW_HEIGHT/2-HEIGHT)/2;
 reg[31:0] previous_row[0:GROUPS-1];
 reg[31:0] previous;
 reg[15:0] x,y;
 reg vs_d,hs_d,active,bad;
 reg pending,selected,odd;
 reg[31:0] current;
 reg[1:0] phase;
 wire[31:0] raw8={raw[39:32],raw[29:22],raw[19:12],raw[9:2]};
 function automatic[15:0] rgb565(input[7:0] tl,tr,bl,br,input[1:0] bayer);
  reg[7:0] r,b,g;reg[8:0] green;
  begin
   case(bayer)
    0:begin b=tl;r=br;green={1'b0,tr}+{1'b0,bl}+1;end
    1:begin r=tl;b=br;green={1'b0,tr}+{1'b0,bl}+1;end
    2:begin b=tr;r=bl;green={1'b0,tl}+{1'b0,br}+1;end
    3:begin r=tr;b=bl;green={1'b0,tl}+{1'b0,br}+1;end
   endcase
   g=green[8:1];rgb565={r[7:3],g[7:2],b[7:3]};
  end
 endfunction
 always @(posedge clk)begin
  pixel_valid<=0;frame_start<=0;frame_end<=0;
  if(reset)begin x<=0;y<=0;vs_d<=0;hs_d<=0;active<=0;bad<=0;frame_bad<=0;
   pending<=0;selected<=0;odd<=0;phase<=0;pixels<=0;previous<=0;current<=0;end
  else begin
   vs_d<=vs;hs_d<=hs;
   // CSI5.15 GENERIC VS is active high across image data. Verified against
   // the licensed vendor RX model; don't infer polarity from demo counters.
   if(!vs_d && vs)begin x<=0;y<=0;active<=1;bad<=0;frame_start<=1;phase<=pattern;end
   if(vs_d && !vs && active)begin
    active<=0;frame_end<=1;frame_bad<=bad || packet_error ||
      (y+(hs_d && !hs))!=RAW_HEIGHT || ((hs_d && !hs) && x!=GROUPS);
   end
   if(active && packet_error)bad<=1;
   // Valid may bubble within a line. Count lines using HS, never valid gaps.
   if(hs_d && !hs && active)begin
    if(x!=GROUPS)bad<=1;
    x<=0;y<=y+1;
   end
   pending<=0;
   if(active && hs && valid)begin
    if(x<GROUPS && y<RAW_HEIGHT)begin
     if(!y[0])previous_row[x]<=raw8;
     else begin previous<=previous_row[x];current<=raw8;pending<=1;end
     selected<=x*2>=CROP_X && x*2<CROP_X+WIDTH && y/2>=CROP_Y && y/2<CROP_Y+HEIGHT;
     x<=x+1;
    end else bad<=1;
   end
   if(pending && selected)begin
    pixels<={rgb565(previous[23:16],previous[31:24],current[23:16],current[31:24],phase),
             rgb565(previous[7:0],previous[15:8],current[7:0],current[15:8],phase)};
    pixel_valid<=1;
   end
  end
 end
endmodule
