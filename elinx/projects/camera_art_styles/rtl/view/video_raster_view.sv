// 640x480 RGB565 -> 960x720 nearest neighbour, preserving 4:3 geometry.
// Every output triple selects source 0,0,1; row 1 reuses row 0 in a
// synchronous 640x16 cache. Exactly 640*480 FIFO reads per good refresh.
// One extra pixel pipeline stage applies equally to RGB/DE/HS/VS/coordinates.
module video_raster_view #(
 parameter integer H_ACTIVE=1280,H_FRONT=110,H_SYNC=40,H_BACK=220,
 parameter integer V_ACTIVE=720,V_FRONT=5,V_SYNC=5,V_BACK=20,
 parameter integer DISPLAY_WIDTH=640,DISPLAY_HEIGHT=480
)(input wire clk,reset,input wire[15:0] fifo_pixel,input wire fifo_empty,fifo_busy,
 output wire fifo_read,output reg refresh_request,input wire refresh_ack,front_valid,
 output reg refresh_window,output reg hsync,vsync,de,output reg[23:0] rgb,
 output reg[31:0] underflow_frames,output reg[11:0] x,y);
 localparam integer HT=H_ACTIVE+H_FRONT+H_SYNC+H_BACK;
 localparam integer VT=V_ACTIVE+V_FRONT+V_SYNC+V_BACK;
 localparam integer HS=H_SYNC+H_BACK,VS=V_SYNC+V_BACK;
 localparam integer IW=DISPLAY_WIDTH*3/2,IH=DISPLAY_HEIGHT*3/2;
 localparam integer IX=HS+(H_ACTIVE-IW)/2,IY=VS+(V_ACTIVE-IH)/2;
 reg[11:0] h,v;
 reg[1:0] xp,yp;
 reg[9:0] source_x;
 reg[15:0] line_cache[0:DISPLAY_WIDTH-1];
 reg[15:0] cache_q,held,pixel0;
 reg frame_bad,line_valid;
 (* async_reg="true",syn_srlstyle="registers" *) reg[1:0] ack_sync,valid_sync;
 wire active=h>=HS && h<HS+H_ACTIVE && v>=VS && v<VS+V_ACTIVE;
 wire image=active && h>=IX && h<IX+IW && v>=IY && v<IY+IH;
 wire repeat_row=yp==1;
 wire new_pixel=xp!=1 && !repeat_row;
 wire ready=ack_sync[1]==refresh_request && valid_sync[1] && !fifo_busy;
 wire missing=image && valid_sync[1] &&
    (!ready || (new_pixel && fifo_empty) || (repeat_row && !line_valid));
 assign fifo_read=image && ready && !frame_bad && new_pixel && !fifo_empty;
 reg a0,image0,valid0,bad0,repeat0,hs0,vs0;
 reg[11:0] x0,y0;
 wire[15:0] selected=repeat0 ? cache_q:pixel0;
 wire[23:0] expanded={selected[15:11],selected[15:13],selected[10:5],selected[10:9],selected[4:0],selected[4:2]};
 function automatic[23:0] bar(input[11:0] bx);
  begin
   if(bx<160)bar=24'hffffff;else if(bx<320)bar=24'hffff00;
   else if(bx<480)bar=24'h00ffff;else if(bx<640)bar=24'h00ff00;
   else if(bx<800)bar=24'hff00ff;else if(bx<960)bar=24'hff0000;
   else if(bx<1120)bar=24'h0000ff;else bar=0;
  end
 endfunction
 // Synchronous RAM read, no memory reset and no asynchronous read port.
 always @(posedge clk)begin
  if(source_x<DISPLAY_WIDTH)cache_q<=line_cache[source_x];
  if(fifo_read)line_cache[source_x]<=fifo_pixel;
 end
 always @(posedge clk)begin
  if(reset)begin ack_sync<=0;valid_sync<=0;end
  else begin ack_sync<={ack_sync[0],refresh_ack};valid_sync<={valid_sync[0],front_valid};end
 end
 always @(posedge clk)begin
  if(reset)begin
   h<=0;v<=0;xp<=0;yp<=0;source_x<=0;held<=0;pixel0<=0;
   frame_bad<=0;line_valid<=0;refresh_request<=0;refresh_window<=0;underflow_frames<=0;
   a0<=0;image0<=0;valid0<=0;bad0<=0;repeat0<=0;hs0<=0;vs0<=0;x0<=0;y0<=0;
   hsync<=0;vsync<=0;de<=0;rgb<=0;x<=0;y<=0;
  end else begin
   refresh_window<=v<VS-1;
   if(h==HT-1)begin
    h<=0;if(v==VT-1)v<=0;else v<=v+1;
    if(v>=IY && v<IY+IH)begin if(yp==2)yp<=0;else yp<=yp+1'b1;end
   end else h<=h+1'b1;
   if(h==0 && v==0)begin
    if(ack_sync[1]==refresh_request)refresh_request<=~refresh_request;
    frame_bad<=0;line_valid<=0;yp<=0;
   end
   if(h==IX-1)begin xp<=0;source_x<=0;end
   if(image)begin
    if(xp==2)xp<=0;else xp<=xp+1'b1;
    if(xp!=0)source_x<=source_x+1'b1;
    if(fifo_read)held<=fifo_pixel;
    if(h==IX+IW-1 && !repeat_row && ready && !frame_bad && !missing)line_valid<=1;
   end
   if(missing && !frame_bad)begin frame_bad<=1;underflow_frames<=underflow_frames+1'b1;line_valid<=0;end
   a0<=active;image0<=image;valid0<=valid_sync[1];bad0<=frame_bad || missing;
   repeat0<=repeat_row;pixel0<=xp==1 ? held:fifo_pixel;
   hs0<=h<H_SYNC;vs0<=v<V_SYNC;x0<=h-HS;y0<=v-VS;
   hsync<=hs0;vsync<=vs0;de<=a0;x<=x0;y<=y0;
   if(!a0)rgb<=0;
   else if(!valid0)rgb<=bar(x0);
   else if(!image0)rgb<=0;
   // Explicit red/yellow checker means display underflow, never style pixels.
   else if(bad0)rgb<=x0[4]^y0[4] ? 24'hff0000:24'hffff00;
   else rgb<=expanded;
  end
 end
endmodule
