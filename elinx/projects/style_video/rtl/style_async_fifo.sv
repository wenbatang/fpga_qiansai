// Portable dual-clock FIFO. A registered read-ahead word provides ready/valid
// semantics; the read pointer releases RAM only after that word is copied.
// Capacity is 2**ADDR_BITS RAM words plus the read-ahead register. Reset both
// domains together: flushing one side alone is deliberately unsupported.
module style_async_fifo #(
    parameter integer WIDTH = 32, parameter integer ADDR_BITS = 10
)(
    input wire wr_clk, rd_clk, async_rst_n,
    input wire [WIDTH-1:0] s_data, input wire s_valid, output wire s_ready,
    output wire [WIDTH-1:0] m_data, output wire m_valid, input wire m_ready,
    output wire [ADDR_BITS:0] wr_level, rd_level
);
    localparam integer DEPTH = 1 << ADDR_BITS;
    reg [WIDTH-1:0] memory [0:DEPTH-1];
    wire wr_rst_n, rd_rst_n;
    style_reset_sync wr_reset(wr_clk, async_rst_n, wr_rst_n);
    style_reset_sync rd_reset(rd_clk, async_rst_n, rd_rst_n);
    reg [ADDR_BITS:0] wbin, wgray, rbin, rgray;
    (* async_reg = "true" *) reg [ADDR_BITS:0] rgray_w1, rgray_w2;
    (* async_reg = "true" *) reg [ADDR_BITS:0] wgray_r1, wgray_r2;
    reg full, out_valid;
    reg [WIDTH-1:0] out_data;
    function [ADDR_BITS:0] gray_to_bin;
        input [ADDR_BITS:0] value;
        integer k;
        begin
            gray_to_bin[ADDR_BITS] = value[ADDR_BITS];
            for (k=ADDR_BITS-1; k>=0; k=k-1)
                gray_to_bin[k] = gray_to_bin[k+1] ^ value[k];
        end
    endfunction
    wire push = s_valid && s_ready;
    wire [ADDR_BITS:0] wnext = wbin + push;
    wire [ADDR_BITS:0] wgnext = (wnext >> 1) ^ wnext;
    wire empty = rgray == wgray_r2;
    wire load = (!out_valid || m_ready) && !empty && rd_rst_n;
    wire [ADDR_BITS:0] rnext = rbin + 1'b1;
    assign s_ready = wr_rst_n && !full;
    assign m_valid = rd_rst_n && out_valid;
    assign m_data = out_data;
    assign wr_level = wbin - gray_to_bin(rgray_w2);
    assign rd_level = gray_to_bin(wgray_r2) - rbin + out_valid;
    always @(posedge wr_clk or negedge wr_rst_n) begin
        if (!wr_rst_n) begin
            wbin<=0; wgray<=0; full<=0; rgray_w1<=0; rgray_w2<=0;
        end else begin
            rgray_w1<=rgray; rgray_w2<=rgray_w1;
            wbin<=wnext; wgray<=wgnext;
            full <= wgnext == {~rgray_w2[ADDR_BITS:ADDR_BITS-1],rgray_w2[ADDR_BITS-2:0]};
        end
    end
    always @(posedge wr_clk) if (push) memory[wbin[ADDR_BITS-1:0]] <= s_data;
    always @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) begin
            rbin<=0; rgray<=0; wgray_r1<=0; wgray_r2<=0; out_valid<=0;
        end else begin
            wgray_r1<=wgray; wgray_r2<=wgray_r1;
            if (load) begin
                rbin<=rnext; rgray<=(rnext>>1)^rnext; out_valid<=1;
            end else if (out_valid && m_ready) out_valid<=0;
        end
    end
    // Separate synchronous RAM read process enables Efinity BRAM inference.
    always @(posedge rd_clk) if (load) out_data <= memory[rbin[ADDR_BITS-1:0]];
endmodule
