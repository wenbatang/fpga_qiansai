// Records: {end_record,bad,frame_id[31:0],word_index[16:0],pixels[127:0]}.
// The frame-end record is essential: reaching the crop's final pixel alone
// does not prove that the CSI frame ended correctly.
module camera_pack_720 #(parameter WIDTH=640,HEIGHT=480)(input wire clk,reset,enable,
 input wire frame_start,frame_end,frame_bad,pixel_valid,input wire[31:0] pixels,
 input wire fifo_full,output reg fifo_write,output reg[178:0] fifo_data,
 output reg[31:0] overflow_frames);
 reg[31:0] frame_id;
 reg[16:0] index;
 reg[1:0] lane;
 reg[127:0] word_data;
 reg active,bad;
 always @(posedge clk)begin
  fifo_write<=0;
  if(reset)begin frame_id<=0;index<=0;lane<=0;word_data<=0;active<=0;bad<=0;fifo_data<=0;overflow_frames<=0;end
  else begin
   if(frame_start)begin frame_id<=frame_id+1;index<=0;lane<=0;word_data<=0;active<=enable;bad<=0;end
   if(active && pixel_valid)begin
    word_data[lane*32+:32]<=pixels;lane<=lane+1;
    if(lane==3)begin
     if(!fifo_full)begin fifo_data<={1'b0,bad,frame_id,index,pixels,word_data[95:0]};fifo_write<=1;end
     else if(!bad)begin bad<=1;overflow_frames<=overflow_frames+1;end
     index<=index+1;
    end
   end
   if(active && frame_end)begin
    active<=0;
    if(!fifo_full)begin
     fifo_data<={1'b1,bad || frame_bad || index!=WIDTH*HEIGHT/8 || lane!=0,frame_id,index,128'd0};fifo_write<=1;
    end else if(!bad)overflow_frames<=overflow_frames+1;
   end
  end
 end
endmodule
