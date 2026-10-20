// Two AXI4 clients -> one DDR port. Client 0 is the least significant slice.
// At most one write and one read transaction outstanding, independently.
// Ownership is captured BEFORE offering AW/AR, and released on B/RLAST.
module style_axi_arbiter #(
    parameter integer ADDR_WIDTH = 32,
    parameter integer DATA_WIDTH = 128,
    parameter integer ID_WIDTH = 6,
    parameter integer READ_CLIENT1_LIMIT = 4
) (
    input wire clk, input wire rst_n,
    input wire [2*ID_WIDTH-1:0] s_axi_awid,
    input wire [2*ADDR_WIDTH-1:0] s_axi_awaddr,
    input wire [15:0] s_axi_awlen,
    input wire [5:0] s_axi_awsize,
    input wire [3:0] s_axi_awburst,
    input wire [1:0] s_axi_awvalid, output reg [1:0] s_axi_awready,
    input wire [2*DATA_WIDTH-1:0] s_axi_wdata,
    input wire [2*(DATA_WIDTH/8)-1:0] s_axi_wstrb,
    input wire [1:0] s_axi_wlast, input wire [1:0] s_axi_wvalid,
    output reg [1:0] s_axi_wready,
    output reg [2*ID_WIDTH-1:0] s_axi_bid,
    output reg [3:0] s_axi_bresp,
    output reg [1:0] s_axi_bvalid, input wire [1:0] s_axi_bready,
    input wire [2*ID_WIDTH-1:0] s_axi_arid,
    input wire [2*ADDR_WIDTH-1:0] s_axi_araddr,
    input wire [15:0] s_axi_arlen,
    input wire [5:0] s_axi_arsize,
    input wire [3:0] s_axi_arburst,
    input wire [1:0] s_axi_arvalid, output reg [1:0] s_axi_arready,
    output reg [2*ID_WIDTH-1:0] s_axi_rid,
    output reg [2*DATA_WIDTH-1:0] s_axi_rdata,
    output reg [3:0] s_axi_rresp,
    output reg [1:0] s_axi_rlast,
    output reg [1:0] s_axi_rvalid, input wire [1:0] s_axi_rready,
    output wire [ID_WIDTH-1:0] m_axi_awid,
    output wire [ADDR_WIDTH-1:0] m_axi_awaddr,
    output wire [7:0] m_axi_awlen,
    output wire [2:0] m_axi_awsize,
    output wire [1:0] m_axi_awburst,
    output wire m_axi_awvalid, input wire m_axi_awready,
    output wire [DATA_WIDTH-1:0] m_axi_wdata,
    output wire [DATA_WIDTH/8-1:0] m_axi_wstrb,
    output wire m_axi_wlast, output wire m_axi_wvalid,
    input wire m_axi_wready,
    input wire [ID_WIDTH-1:0] m_axi_bid,
    input wire [1:0] m_axi_bresp,
    input wire m_axi_bvalid, output wire m_axi_bready,
    output wire [ID_WIDTH-1:0] m_axi_arid,
    output wire [ADDR_WIDTH-1:0] m_axi_araddr,
    output wire [7:0] m_axi_arlen,
    output wire [2:0] m_axi_arsize,
    output wire [1:0] m_axi_arburst,
    output wire m_axi_arvalid, input wire m_axi_arready,
    input wire [ID_WIDTH-1:0] m_axi_rid,
    input wire [DATA_WIDTH-1:0] m_axi_rdata,
    input wire [1:0] m_axi_rresp,
    input wire m_axi_rlast, input wire m_axi_rvalid,
    output wire m_axi_rready
);
    reg wr_active, wr_owner, wr_next, aw_seen, w_seen;
    reg rd_active, rd_owner, ar_seen;
    reg [31:0] display_grants;
    assign m_axi_awid = s_axi_awid[wr_owner*ID_WIDTH +: ID_WIDTH];
    assign m_axi_awaddr = s_axi_awaddr[wr_owner*ADDR_WIDTH +: ADDR_WIDTH];
    assign m_axi_awlen = s_axi_awlen[wr_owner*8 +: 8];
    assign m_axi_awsize = s_axi_awsize[wr_owner*3 +: 3];
    assign m_axi_awburst = s_axi_awburst[wr_owner*2 +: 2];
    assign m_axi_awvalid = wr_active && !aw_seen && s_axi_awvalid[wr_owner];
    assign m_axi_wdata = s_axi_wdata[wr_owner*DATA_WIDTH +: DATA_WIDTH];
    assign m_axi_wstrb = s_axi_wstrb[wr_owner*(DATA_WIDTH/8) +: DATA_WIDTH/8];
    assign m_axi_wlast = s_axi_wlast[wr_owner];
    assign m_axi_wvalid = wr_active && !w_seen && s_axi_wvalid[wr_owner];
    assign m_axi_bready = wr_active && aw_seen && w_seen && s_axi_bready[wr_owner];
    assign m_axi_arid = s_axi_arid[rd_owner*ID_WIDTH +: ID_WIDTH];
    assign m_axi_araddr = s_axi_araddr[rd_owner*ADDR_WIDTH +: ADDR_WIDTH];
    assign m_axi_arlen = s_axi_arlen[rd_owner*8 +: 8];
    assign m_axi_arsize = s_axi_arsize[rd_owner*3 +: 3];
    assign m_axi_arburst = s_axi_arburst[rd_owner*2 +: 2];
    assign m_axi_arvalid = rd_active && !ar_seen && s_axi_arvalid[rd_owner];
    assign m_axi_rready = rd_active && ar_seen && s_axi_rready[rd_owner];

    always @* begin
        s_axi_awready = 0; s_axi_wready = 0;
        s_axi_bid = 0; s_axi_bresp = 0; s_axi_bvalid = 0;
        s_axi_arready = 0; s_axi_rid = 0; s_axi_rdata = 0;
        s_axi_rresp = 0; s_axi_rlast = 0; s_axi_rvalid = 0;
        if (wr_active) begin
            s_axi_awready[wr_owner] = !aw_seen && m_axi_awready;
            s_axi_wready[wr_owner] = !w_seen && m_axi_wready;
            s_axi_bid[wr_owner*ID_WIDTH +: ID_WIDTH] = m_axi_bid;
            s_axi_bresp[wr_owner*2 +: 2] = m_axi_bresp;
            s_axi_bvalid[wr_owner] = aw_seen && w_seen && m_axi_bvalid;
        end
        if (rd_active) begin
            s_axi_arready[rd_owner] = !ar_seen && m_axi_arready;
            s_axi_rid[rd_owner*ID_WIDTH +: ID_WIDTH] = m_axi_rid;
            s_axi_rdata[rd_owner*DATA_WIDTH +: DATA_WIDTH] = m_axi_rdata;
            s_axi_rresp[rd_owner*2 +: 2] = m_axi_rresp;
            s_axi_rlast[rd_owner] = ar_seen && m_axi_rlast;
            s_axi_rvalid[rd_owner] = ar_seen && m_axi_rvalid;
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            wr_active <= 0; wr_owner <= 0; wr_next <= 0;
            aw_seen <= 0; w_seen <= 0;
            rd_active <= 0; rd_owner <= 1; ar_seen <= 0; display_grants <= 0;
        end else begin
            if (!wr_active) begin
                if (s_axi_awvalid != 0) begin
                    wr_owner <= s_axi_awvalid == 2'b11 ? wr_next : s_axi_awvalid[1];
                    wr_active <= 1; aw_seen <= 0; w_seen <= 0;
                end
            end else begin
                if (m_axi_awvalid && m_axi_awready) aw_seen <= 1;
                if (m_axi_wvalid && m_axi_wready && m_axi_wlast) w_seen <= 1;
                if (m_axi_bvalid && m_axi_bready) begin
                    wr_active <= 0; wr_next <= !wr_owner;
                end
            end
            if (!rd_active) begin
                if (s_axi_arvalid != 0) begin
                    rd_owner <= s_axi_arvalid[1] &&
                        (!s_axi_arvalid[0] || display_grants < READ_CLIENT1_LIMIT);
                    rd_active <= 1; ar_seen <= 0;
                end
            end else begin
                if (m_axi_arvalid && m_axi_arready) ar_seen <= 1;
                if (m_axi_rvalid && m_axi_rready && m_axi_rlast) begin
                    rd_active <= 0;
                    if (!rd_owner) display_grants <= 0;
                    else if (display_grants < READ_CLIENT1_LIMIT)
                        display_grants <= display_grants + 1'b1;
                end
            end
        end
    end
endmodule
