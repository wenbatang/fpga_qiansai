// KEY2..KEY5: active low; external 4.7k pull-ups to Bank14 3.3V.
// Reset disarms each key until a debounced release. Held keys do not repeat.
module style_keys #(parameter integer DEBOUNCE_CYCLES=1000000)
(input wire clk,reset,input wire [3:0] keys_n,
 output reg event_valid,output reg [1:0] event_style);
    (* ASYNC_REG="TRUE" *) reg [3:0] sync_meta,sync_keys;
    reg [3:0] stable,armed,presses;
    localparam integer BITS=$clog2(DEBOUNCE_CYCLES+1);
    reg [BITS-1:0] count [0:3];
    integer i;
    always @(posedge clk)begin
        if(reset)begin sync_meta<=4'hf;sync_keys<=4'hf;end
        else begin sync_meta<=keys_n;sync_keys<=sync_meta;end
    end
    always @(posedge clk)begin
        event_valid<=0;presses<=0;
        if(reset)begin
            stable<=0;armed<=0;event_style<=0;
            for(i=0;i<4;i=i+1)count[i]<=0;
        end else begin
            for(i=0;i<4;i=i+1)begin
                if(sync_keys[i]==stable[i])count[i]<=0;
                else if(count[i]==DEBOUNCE_CYCLES-1)begin
                    count[i]<=0;stable[i]<=sync_keys[i];
                    if(sync_keys[i])armed[i]<=1;
                    else if(armed[i])begin presses[i]<=1;armed[i]<=0;end
                end else count[i]<=count[i]+1'b1;
            end
            // Simultaneous keys: KEY2 > KEY3 > KEY4 > KEY5.
            if(presses[0])begin event_valid<=1;event_style<=0;end
            else if(presses[1])begin event_valid<=1;event_style<=1;end
            else if(presses[2])begin event_valid<=1;event_style<=2;end
            else if(presses[3])begin event_valid<=1;event_style<=3;end
        end
    end
endmodule
