// Efinix FIFO IP 1.3, 128-bit UI writes -> sixteen-bit FWFT pixels.
// ASYM_WIDTH_RATIO=1 is the IP's encoded 8:1 ratio, not numeric ratio 1.
module pixel_fifo_efx(input wire rst,wr_clk,rd_clk,input wire [127:0] din,
 input wire wr_en,rd_en,output wire [15:0] dout,output wire full,empty,
 output wire wr_rst_busy,rd_rst_busy,output wire [10:0] wr_data_count);
    (* async_reg="true",syn_srlstyle="registers" *) reg [7:0] wr_reset=8'hff,rd_reset=8'hff;
    (* async_reg="true",syn_srlstyle="registers" *) reg [1:0] rd_busy_sync=2'b11;
    always @(posedge wr_clk or posedge rst)
        if(rst)begin wr_reset<=8'hff;rd_busy_sync<=2'b11;end
        else begin wr_reset<={wr_reset[6:0],1'b0};rd_busy_sync<={rd_busy_sync[0],rd_reset[7]};end
    always @(posedge rd_clk or posedge rst)
        if(rst)rd_reset<=8'hff;
        else rd_reset<={rd_reset[6:0],1'b0};
    assign wr_rst_busy=wr_reset[7] || rd_busy_sync[1];
    assign rd_rst_busy=rd_reset[7];
    // The bundled asymmetrical RAM emits the most-significant lane first.
    // AXI raw pixels are little-endian, earliest pixel in din[15:0].
    wire [127:0] reversed;
    genvar i;
    generate for(i=0;i<8;i=i+1)begin:lanes
        assign reversed[(7-i)*16+:16]=din[i*16+:16];
    end endgenerate
    efx_fifo_wrapper #(.FAMILY("TITANIUM"),.SYNC_CLK(0),.SYNC_STAGE(2),
      .BYPASS_RESET_SYNC(0),.MODE("FWFT"),.DEPTH(1024),.DATA_WIDTH(128),
      .ASYM_WIDTH_RATIO(1),.PIPELINE_REG(1),.OUTPUT_REG(0)) storage(
      // This bundled wrapper does not forward the separate reset ports.
      // Use its common asynchronous reset and internal synchronized release.
      .a_rst_i(rst),.a_wr_rst_i(1'b0),.a_rd_rst_i(1'b0),
      .clk_i(1'b0),.wr_clk_i(wr_clk),.rd_clk_i(rd_clk),
      .wr_en_i(wr_en && !wr_rst_busy),.rd_en_i(rd_en && !rd_rst_busy),.wdata(reversed),.rdata(dout),
      .full_o(full),.empty_o(empty),.wr_datacount_o(wr_data_count),
      .almost_full_o(),.prog_full_o(),.overflow_o(),.wr_ack_o(),.datacount_o(),
      .almost_empty_o(),.prog_empty_o(),.underflow_o(),.rd_valid_o(),.rd_datacount_o(),.rst_busy());
endmodule
