// KEY0:RAW->STYLE->SPLIT; KEY1:next; KEY2:previous; KEY3:toggle overlay.
// Low-active3.3V inputs, two FF synchronization and10ms debounce.
module style_keys47 #(parameter integer DEBOUNCE_CYCLES=1000000,PREVIEW_HOLD_CYCLES=50000000,LEARN_HOLD_CYCLES=100000000)(
 input wire clk,reset,input wire[3:0]keys_n,input wire[3:0]current_style,input wire learning_active,gesture_confirm,
 output reg event_valid,output reg[5:0]event_style,output wire raw_mode,
 output reg[1:0]display_mode,output wire split_mode,output wire learn_event,capture_event,mode_event,output reg ui_visible);
 (* async_reg="true",syn_srlstyle="registers" *)reg[3:0]sync_meta,sync_keys;
 reg[3:0]stable,armed,presses;
 localparam BITS=$clog2(DEBOUNCE_CYCLES+1);reg[BITS-1:0]count[0:3];integer i;
 localparam LEARN_BITS=$clog2(LEARN_HOLD_CYCLES+1);
 reg[LEARN_BITS-1:0]learn_count;reg learn_armed;
 wire both_style_keys=!stable[1] && !stable[2] && !sync_keys[1] && !sync_keys[2];
 wire learn_fire=both_style_keys && learn_armed && learn_count==LEARN_HOLD_CYCLES-1;
 // These are same-UI-cycle strobes, visible before the edge that changes the
 // view. A simultaneous guarded gesture must be rejected at that same edge.
 wire ui_ready=!reset;
 assign learn_event=ui_ready && learn_fire;
 assign capture_event=ui_ready && learning_active && presses[0] && !learn_fire;
 assign mode_event=ui_ready && !learning_active && presses[0] && !learn_fire;
 assign raw_mode=display_mode==0;assign split_mode=display_mode==2;
 always @(posedge clk)begin
  if(reset)begin sync_meta<=4'hf;sync_keys<=4'hf;end else begin sync_meta<=keys_n;sync_keys<=sync_meta;end
 end
 always @(posedge clk)begin
  event_valid<=0;presses<=0;
  if(reset)begin stable<=0;armed<=0;display_mode<=0;event_style<=0;learn_count<=0;learn_armed<=1;ui_visible<=1;for(i=0;i<4;i=i+1)count[i]<=0;end
  else begin
   for(i=0;i<4;i=i+1)begin
    if(sync_keys[i]==stable[i])count[i]<=0;
    else if(count[i]==DEBOUNCE_CYCLES-1)begin
     count[i]<=0;stable[i]<=sync_keys[i];
     if(sync_keys[i])armed[i]<=1;else if(armed[i])begin presses[i]<=1;armed[i]<=0;end
    end else count[i]<=count[i]+1'b1;
   end
   begin
    if(presses[3])ui_visible<=!ui_visible;
    // Only a debounced release rearms the long chord. A raw synchronizer
    // glitch may interrupt the hold count, but cannot toggle learning twice.
    if(stable[1] || stable[2])begin learn_count<=0;learn_armed<=1;end
    else if(!both_style_keys)learn_count<=0;
    else if(learn_armed)begin
     if(learn_fire)learn_armed<=0;
     else learn_count<=learn_count+1'b1;
    end
    if(learning_active || learn_fire)display_mode<=0;
    else if(presses[0])display_mode<=display_mode==2?0:display_mode+1'b1;
    else if(gesture_confirm && display_mode==0)display_mode<=1;
    if(presses[1] && !presses[2])begin event_style<=current_style>=9?0:{2'b00,current_style}+1'b1;event_valid<=1;end
    else if(presses[2] && !presses[1])begin event_style<=current_style==0 || current_style>9?9:{2'b00,current_style}-1'b1;event_valid<=1;end
   end
  end
 end
endmodule
