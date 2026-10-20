// Reset is asynchronous on assertion and local-clock synchronous on release.
module style_reset_sync #(parameter integer STAGES = 3)(
    input wire clk, input wire async_rst_n, output wire rst_n
);
    (* async_reg = "true" *) reg [STAGES-1:0] pipe;
    always @(posedge clk or negedge async_rst_n)
        if (!async_rst_n) pipe <= 0;
        else pipe <= {pipe[STAGES-2:0], 1'b1};
    assign rst_n = pipe[STAGES-1];
endmodule
