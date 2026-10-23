// KEY2 next / KEY3 previous, active low; KEY4/KEY5 reserved inputs.
// Synchronize then debounce. Held keys never repeat; both keys cancel.
module style_keys #(parameter integer DEBOUNCE_CYCLES=1000000)
(input wire clk,reset,input wire [3:0] keys_n,
 output reg event_valid,output reg [2:0] event_style);
 (* ASYNC_REG="TRUE" *) reg [1:0] sync_meta,sync_keys;
 reg[1:0] stable,armed,presses;
 reg[2:0] choice;
 localparam integer BITS=$clog2(DEBOUNCE_CYCLES+1);
 reg[BITS-1:0] count[0:1];integer i;
 always @(posedge clk)begin
  if(reset)begin sync_meta<=3;sync_keys<=3;end
  else begin sync_meta<=keys_n[1:0];sync_keys<=sync_meta;end
 end
 always @(posedge clk)begin
  event_valid<=0;presses<=0;
  if(reset)begin
   stable<=0;armed<=0;choice<=0;event_style<=0;
   for(i=0;i<2;i=i+1)count[i]<=0;
  end else begin
   for(i=0;i<2;i=i+1)begin
    if(sync_keys[i]==stable[i])count[i]<=0;
    else if(count[i]==DEBOUNCE_CYCLES-1)begin
     count[i]<=0;stable[i]<=sync_keys[i];
     if(sync_keys[i])armed[i]<=1;
     else if(armed[i])begin presses[i]<=1;armed[i]<=0;end
    end else count[i]<=count[i]+1'b1;
   end
   if(presses==2'b01)begin
    choice<=choice==5 ? 0:choice+1'b1;
    event_style<=choice==5 ? 0:choice+1'b1;event_valid<=1;
   end else if(presses==2'b10)begin
    choice<=choice==0 ? 5:choice-1'b1;
    event_style<=choice==0 ? 5:choice-1'b1;event_valid<=1;
   end
  end
 end
endmodule
