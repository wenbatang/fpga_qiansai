// V4 KEY0..KEY3: active low, external pull-ups; TL/BR 3.3V.
// Reset disarms each key until a debounced release. Held keys do not repeat.
module style_keys47 #(parameter integer DEBOUNCE_CYCLES=1000000,PREVIEW_HOLD_CYCLES=50000000)
(input wire clk,reset,input wire [3:0] keys_n,
 output reg event_valid,output reg [5:0] event_style,output reg raw_mode);
    (* async_reg="true", syn_srlstyle="registers" *) reg [3:0] sync_meta,sync_keys;
    reg [3:0] stable,armed,presses;
    localparam integer BITS=$clog2(DEBOUNCE_CYCLES+1);
    reg [BITS-1:0] count [0:3];
    integer i;
    localparam integer HB=$clog2(PREVIEW_HOLD_CYCLES+1);
    reg[HB-1:0] hold_count;reg pair_fired,pair_armed;
    always @(posedge clk)begin
        if(reset)begin sync_meta<=4'hf;sync_keys<=4'hf;end
        else begin sync_meta<=keys_n;sync_keys<=sync_meta;end
    end
    always @(posedge clk)begin
        event_valid<=0;presses<=0;
        if(reset)begin
            stable<=0;armed<=0;event_style<=0;raw_mode<=1;hold_count<=0;pair_fired<=0;pair_armed<=0;
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
            // Startup raw preview. A debounced KEY1+KEY2 hold returns to
            // raw; either released key rearms it. Existing KEY0+KEY3 resets.
            if(stable[1] && stable[2])pair_armed<=1;
            if(stable[1] || stable[2])begin hold_count<=0;pair_fired<=0;end
            else if(pair_armed && !pair_fired)begin
                if(hold_count==PREVIEW_HOLD_CYCLES-1)begin
                    raw_mode<=1;pair_fired<=1;
                end else hold_count<=hold_count+1'b1;
            end
            // Simultaneous keys: KEY0 > KEY1 > KEY2 > KEY3.
            if(presses[0])begin event_valid<=1;event_style<=0;raw_mode<=0;end
            else if(presses[1])begin event_valid<=1;event_style<=1;raw_mode<=0;end
            else if(presses[2])begin event_valid<=1;event_style<=2;raw_mode<=0;end
            else if(presses[3])begin event_valid<=1;event_style<=3;raw_mode<=0;end
        end
    end
endmodule
