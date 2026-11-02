// Power-on delay only. All four low-active keys are handled in the UI domain;
// KEY3 toggles overlays and must never reset the board or erase enrollment.
module board_boot #(parameter integer POWER_CYCLES=2500000,HOLD_CYCLES=25000000)
(input wire clk,input wire [3:0] keys_n,output wire reset_n);
    reg [$clog2(POWER_CYCLES+1)-1:0] power_count=0;
    always @(posedge clk)begin
        if(power_count<POWER_CYCLES)power_count<=power_count+1'b1;
    end
    assign reset_n=power_count==POWER_CYCLES;
endmodule
