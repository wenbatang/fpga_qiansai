module hdmi_reset_syn(
    input   logic   reset_n     ,
    input   logic   clk         ,

    output  logic   syn_reset
);

logic   reset1, reset2      ;
assign  syn_reset = reset2  ;

always_ff @(posedge clk or negedge reset_n) begin
    if (!reset_n) begin
        reset1 <= 1'b1      ;
        reset2 <= 1'b1      ;    
    end else begin
        reset1 <= 1'b0      ;
        reset2 <= reset1    ;
    end
end

endmodule