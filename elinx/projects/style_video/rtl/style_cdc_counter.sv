// Only for monotonically incrementing counters (one count per source edge).
module style_cdc_counter #(parameter integer WIDTH=32)(
    input wire src_clk, src_rst_n, input wire [WIDTH-1:0] src_count,
    input wire dst_clk, dst_rst_n, output reg [WIDTH-1:0] dst_count
);
    reg [WIDTH-1:0] gray;
    (* async_reg="true" *) reg [WIDTH-1:0] sync1,sync2;
    integer k;
    always @(posedge src_clk or negedge src_rst_n)
        if(!src_rst_n) gray<=0; else gray<=(src_count>>1)^src_count;
    always @(posedge dst_clk or negedge dst_rst_n)
        if(!dst_rst_n) begin sync1<=0; sync2<=0; end
        else begin sync1<=gray; sync2<=sync1; end
    always @* begin
        dst_count[WIDTH-1]=sync2[WIDTH-1];
        for(k=WIDTH-2;k>=0;k=k-1) dst_count[k]=dst_count[k+1]^sync2[k];
    end
endmodule
