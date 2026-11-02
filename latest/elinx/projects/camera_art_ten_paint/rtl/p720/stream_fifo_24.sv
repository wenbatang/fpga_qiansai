// 24-bit atomic asynchronous stream, with reset release in each clock domain.
module stream_fifo_24(input wire arst,wr_clk,rd_clk,input wire[23:0]din,
 input wire wr_en,rd_en,output wire[23:0]dout,output wire full,empty,
 output wire wr_busy,rd_busy);
 (* async_reg="true",syn_srlstyle="registers" *)reg[7:0]wr_reset=8'hff,rd_reset=8'hff;
 (* async_reg="true",syn_srlstyle="registers" *)reg[1:0]rd_busy_sync=3;
 always @(posedge wr_clk or posedge arst)
  if(arst)begin wr_reset<=8'hff;rd_busy_sync<=3;end
  else begin wr_reset<={wr_reset[6:0],1'b0};rd_busy_sync<={rd_busy_sync[0],rd_reset[7]};end
 always @(posedge rd_clk or posedge arst)
  if(arst)rd_reset<=8'hff;else rd_reset<={rd_reset[6:0],1'b0};
 assign wr_busy=wr_reset[7] || rd_busy_sync[1];assign rd_busy=rd_reset[7];
 efx_fifo_wrapper #(.FAMILY("TITANIUM"),.SYNC_CLK(0),.SYNC_STAGE(2),.BYPASS_RESET_SYNC(0),
  .MODE("FWFT"),.DEPTH(128),.DATA_WIDTH(24),.PIPELINE_REG(1),.OUTPUT_REG(0)) storage(
  .a_rst_i(arst),.a_wr_rst_i(1'b0),.a_rd_rst_i(1'b0),.clk_i(1'b0),.wr_clk_i(wr_clk),.rd_clk_i(rd_clk),
  .wr_en_i(wr_en && !wr_busy),.rd_en_i(rd_en && !rd_busy),.wdata(din),.rdata(dout),
  .full_o(full),.empty_o(empty),.wr_datacount_o(),.almost_full_o(),.prog_full_o(),.overflow_o(),.wr_ack_o(),.datacount_o(),
  .almost_empty_o(),.prog_empty_o(),.underflow_o(),.rd_valid_o(),.rd_datacount_o(),.rst_busy());
endmodule
