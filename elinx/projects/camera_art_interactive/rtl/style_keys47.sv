// KEY0:RAW->STYLE->SPLIT; KEY1:next style; KEY2:previous; KEY3:hold reset.
// Low-active3.3V inputs, two FF synchronization and10ms debounce.
module style_keys47 #(parameter integer DEBOUNCE_CYCLES=1000000,PREVIEW_HOLD_CYCLES=50000000)(
 input wire clk,reset,input wire[3:0]keys_n,
 output reg event_valid,output reg[5:0]event_style,output wire raw_mode,
 output reg[1:0]display_mode,output wire split_mode);
 (* async_reg="true",syn_srlstyle="registers" *)reg[3:0]sync_meta,sync_keys;
 reg[3:0]stable,armed,presses;
 localparam BITS=$clog2(DEBOUNCE_CYCLES+1);reg[BITS-1:0]count[0:3];integer i;
 assign raw_mode=display_mode==0;assign split_mode=display_mode==2;
 always @(posedge clk)begin
  if(reset)begin sync_meta<=4'hf;sync_keys<=4'hf;end else begin sync_meta<=keys_n;sync_keys<=sync_meta;end
 end
 always @(posedge clk)begin
  event_valid<=0;presses<=0;
  if(reset)begin stable<=0;armed<=0;display_mode<=0;event_style<=0;for(i=0;i<4;i=i+1)count[i]<=0;end
  else begin
   for(i=0;i<4;i=i+1)begin
    if(sync_keys[i]==stable[i])count[i]<=0;
    else if(count[i]==DEBOUNCE_CYCLES-1)begin
     count[i]<=0;stable[i]<=sync_keys[i];
     if(sync_keys[i])armed[i]<=1;else if(armed[i])begin presses[i]<=1;armed[i]<=0;end
    end else count[i]<=count[i]+1'b1;
   end
   if(stable[3] && sync_keys[3])begin
    if(presses[0])display_mode<=display_mode==2?0:display_mode+1'b1;
    if(presses[1] && !presses[2])begin event_style<=event_style==3?0:event_style+1'b1;event_valid<=1;end
    else if(presses[2] && !presses[1])begin event_style<=event_style==0?3:event_style-1'b1;event_valid<=1;end
   end
  end
 end
endmodule
