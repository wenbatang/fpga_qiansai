// All four V4 keys select styles. KEY0+KEY3 held for one second reset
// the whole design; the 25MHz board oscillator continues during PLL reset.
module board_boot #(parameter integer POWER_CYCLES=2500000,HOLD_CYCLES=25000000)
(input wire clk,input wire [3:0] keys_n,output wire reset_n);
    reg [$clog2(POWER_CYCLES+1)-1:0] power_count=0;
    reg [$clog2(HOLD_CYCLES+1)-1:0] hold_count=0;
    (* async_reg="true",syn_srlstyle="registers" *) reg [3:0] meta=4'hf,sync_keys=4'hf;
    always @(posedge clk)begin
        meta<=keys_n;sync_keys<=meta;
        if(power_count<POWER_CYCLES)power_count<=power_count+1'b1;
        if(!sync_keys[0] && !sync_keys[3])begin
            if(hold_count<HOLD_CYCLES)hold_count<=hold_count+1'b1;
        end else hold_count<=0;
    end
    assign reset_n=power_count==POWER_CYCLES && hold_count!=HOLD_CYCLES;
endmodule
