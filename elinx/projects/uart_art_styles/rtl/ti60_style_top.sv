`include "style_weights.vh"
`include "style_profile.vh"
module ti60_style_top #(parameter integer PROC_WIDTH=`STYLE_PROC_WIDTH,PROC_HEIGHT=`STYLE_PROC_HEIGHT,UART_BAUD=2000000,UART_PAYLOAD_BYTES=16384)
(input wire CLK_25M,CLK_27M,core_clk,hdmi_tx_slow_clk,
 input wire sdram_clk,rx_cal_clk,tx_cal_clk,tx_cal_clk_90edge,pll_locked,user_pll_locked,core_pll_locked,
 input wire [3:0] style_keys_n,input wire uart_rx,output wire uart_tx,
 output wire DDR3_PLL_RSTN,USER_PLL_RSTN,CORE_PLL_RSTN,
 output wire [9:0] tmds_tx_clk_TX_DATA,tmds_tx_data0_TX_DATA,tmds_tx_data1_TX_DATA,tmds_tx_data2_TX_DATA,
 output wire tmds_tx_clk_TX_RST,tmds_tx_data0_TX_RST,tmds_tx_data1_TX_RST,tmds_tx_data2_TX_RST,
 output wire tmds_tx_clk_TX_OE,tmds_tx_data0_TX_OE,tmds_tx_data1_TX_OE,tmds_tx_data2_TX_OE,
 output          [2:0]           pll_shift,  
output          [4:0]           pll_shift_sel,
output                          pll_shift_ena,  


output                          ddr_ck_hi,
output                          ddr_ck_lo,
output                          ddr_reset_n,
output          [1-1:0] ddr_cke,     
output          [14-1:0] ddr_addr,
output          [3-1:0]ddr_ba,
output                          ddr_cas_n,
output          [1-1:0] 
                                ddr_cs_n,
output                          ddr_ras_n,
output                          ddr_we_n,

input           [2-1:0] ddr_dqs_in_hi,
input           [2-1:0] ddr_dqs_in_lo,
input           [16-1:0]  ddr_dq_in_hi,
input           [16-1:0]  ddr_dq_in_lo,

output          [2-1:0] ddr_dqs_oe,
output          [2-1:0] ddr_dqs_oe_n,
output          [16-1:0]  ddr_dq_oe,    
output          [2-1:0] ddr_dqs_out_hi,
output          [2-1:0] ddr_dqs_out_lo,
output          [16-1:0]  ddr_dq_out_hi,
output          [16-1:0]  ddr_dq_out_lo,
output          [2-1:0]  ddr_dm_hi,
output          [2-1:0]  ddr_dm_lo,
output          [1-1:0] ddr_odt);
 wire ui_clk=core_clk,pixel_clk=hdmi_tx_slow_clk;
 wire sys_rst_n,reset_ui,reset_pixel,ddr_reset,calibrated;
 board_boot boot(.clk(CLK_25M),.keys_n(style_keys_n),.reset_n(sys_rst_n));
 assign DDR3_PLL_RSTN=sys_rst_n;assign USER_PLL_RSTN=sys_rst_n;assign CORE_PLL_RSTN=sys_rst_n;
 reset_sync ddr_rst(.clk(ui_clk),.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked),.reset(ddr_reset));
 reset_sync rst_ui(.clk(ui_clk),.async_reset(ddr_reset || !calibrated),.reset(reset_ui));
 reset_sync rst_pixel(.clk(pixel_clk),.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked || !calibrated),.reset(reset_pixel));
    wire [7:0] rx_data,tx_data;
    wire rx_valid,rx_error,tx_valid,tx_ready;
    uart_rx_8n1 #(.CLOCK_HZ(100000000),.BAUD(UART_BAUD)) receiver(.clk(ui_clk),.reset(reset_ui),.rx(uart_rx),
        .data(rx_data),.valid(rx_valid),.framing_error(rx_error));
    uart_tx_8n1 #(.CLOCK_HZ(100000000),.BAUD(UART_BAUD)) transmitter(.clk(ui_clk),.reset(reset_ui),.data(tx_data),
        .valid(tx_valid),.ready(tx_ready),.tx(uart_tx));
    wire packet_valid,bad_packet,packet_consume;
    localparam integer PACKET_ADDRESS_BITS=$clog2(UART_PAYLOAD_BYTES+25);
    wire [PACKET_ADDRESS_BITS-1:0] packet_length,packet_address;
    wire [7:0] packet_data;
    wire [31:0] packet_crc,packet_errors;
    packet_rx_cobs #(.MAX_BYTES(UART_PAYLOAD_BYTES+24),.TIMEOUT_CYCLES(100000000)) packets(.clk(ui_clk),.reset(reset_ui),.byte_data(rx_data),.byte_valid(rx_valid),
        .framing_error(rx_error),.consume(packet_consume),.read_address(packet_address),.read_data(packet_data),
        .packet_valid(packet_valid),.packet_length(packet_length),.packet_crc(packet_crc),
        .bad_packet(bad_packet),.error_count(packet_errors));
    wire reply_valid,reply_ready;
    wire [7:0] reply_command,reply_status;
    wire [15:0] reply_sequence;
    wire [31:0] reply_frame,reply_offset;
    packet_reply #(.WIDTH(PROC_WIDTH),.HEIGHT(PROC_HEIGHT)) replies(.clk(ui_clk),.reset(reset_ui),.valid(reply_valid),.ready(reply_ready),
        .command(reply_command),.status(reply_status),.sequence_id(reply_sequence),
        .frame_id(reply_frame),.accepted_offset(reply_offset),.tx_data(tx_data),.tx_valid(tx_valid),.tx_ready(tx_ready));

    wire front_bank,front_valid,commit_valid,commit_bank,commit_ack,session_active;
    wire writer_commit_valid,writer_commit_bank;
    wire [31:0] writer_commit_frame;
    wire writer_commit_ack,writer_commit_fail;
    wire [1:0] selected_style;
    wire [31:0] front_frame,commit_frame,accepted_frames,rejected_packets;
    wire [29:0] awaddr,araddr;
    wire [29:0] raw_awaddr,cnn_awaddr,cnn_araddr,display_araddr;
    wire [127:0] raw_wdata,cnn_wdata,cnn_rdata,display_rdata;
    wire raw_awvalid,raw_awready,raw_wvalid,raw_wready,raw_bvalid,raw_bready;
    wire cnn_awvalid,cnn_awready,cnn_wvalid,cnn_wready,cnn_bvalid,cnn_bready;
    wire cnn_arvalid,cnn_arready,cnn_rvalid,cnn_rlast,cnn_rready;
    wire display_arvalid,display_arready,display_rvalid,display_rlast,display_rready;
    wire [1:0] cnn_rresp,display_rresp;
    wire engine_start,display_commit_valid,output_bank;
    wire [31:0] output_frame;
    wire engine_busy,engine_done,engine_error;
    wire [31:0] engine_cycles;
    wire [31:0] last_inference_cycles,inference_frames,inference_errors;
    wire write_owner;
    wire writer_idle,source_invalidate,key_event,source_valid;
    wire [1:0] key_style,requested_style,engine_style;
    style_keys keys(.clk(ui_clk),.reset(reset_ui),.keys_n(style_keys_n),.event_valid(key_event),.event_style(key_style));
    assign awaddr=write_owner ? cnn_awaddr : raw_awaddr;
    assign awvalid=write_owner ? cnn_awvalid : raw_awvalid;
    assign wdata=write_owner ? cnn_wdata : raw_wdata;
    assign wvalid=write_owner ? cnn_wvalid : raw_wvalid;
    assign bready=write_owner ? cnn_bready : raw_bready;
    assign raw_awready=awready && !write_owner;
    assign raw_wready=wready && !write_owner;
    assign raw_bvalid=bvalid && !write_owner;
    assign cnn_awready=awready && write_owner;
    assign cnn_wready=wready && write_owner;
    assign cnn_bvalid=bvalid && write_owner;
    assign commit_valid=display_commit_valid;
    assign commit_bank=output_bank;
    assign commit_frame=output_frame;
    style_key_control control(.clk(ui_clk),.reset(reset_ui),.writer_commit_valid(writer_commit_valid),
        .writer_idle(writer_idle && !packet_valid && !rx_valid),.source_invalidate(source_invalidate),
        .key_event(key_event),.key_style(key_style),.requested_style(requested_style),.engine_style(engine_style),.source_valid(source_valid),
        .writer_commit_frame(writer_commit_frame),.front_bank(front_bank),.engine_done(engine_done),
        .engine_error(engine_error),.engine_cycles(engine_cycles),.display_commit_ack(commit_ack),
        .engine_start(engine_start),.writer_commit_ack(writer_commit_ack),.writer_commit_fail(writer_commit_fail),
        .display_commit_valid(display_commit_valid),.output_bank(output_bank),.output_frame(output_frame),
        .last_inference_cycles(last_inference_cycles),.inference_frames(inference_frames),
        .inference_errors(inference_errors),.write_owner(write_owner));
    style_tile_engine #(.WIDTH(PROC_WIDTH),.HEIGHT(PROC_HEIGHT),`STYLE_WEIGHT_PARAMETERS) engine(
        .clk(ui_clk),.reset(reset_ui),.start(engine_start),.style(engine_style),.output_bank(output_bank),
        .busy(engine_busy),.done(engine_done),.error(engine_error),.cycles(engine_cycles),
        .araddr(cnn_araddr),.arvalid(cnn_arvalid),.arready(cnn_arready),
        .rdata(cnn_rdata),.rresp(cnn_rresp),.rvalid(cnn_rvalid),.rlast(cnn_rlast),.rready(cnn_rready),
        .awaddr(cnn_awaddr),.awvalid(cnn_awvalid),.awready(cnn_awready),
        .wdata(cnn_wdata),.wvalid(cnn_wvalid),.wready(cnn_wready),.bresp(bresp),.bvalid(cnn_bvalid),.bready(cnn_bready));
    style_read_arbiter read_bus(
        .clk(ui_clk),.reset(reset_ui),.display_addr(display_araddr),.display_valid(display_arvalid),.display_ready(display_arready),
        .style_addr(cnn_araddr),.style_valid(cnn_arvalid),.style_ready(cnn_arready),
        .araddr(araddr),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rresp(rresp),.rvalid(rvalid),.rlast(rlast),.rready(rready),
        .display_data(display_rdata),.display_resp(display_rresp),.display_rvalid(display_rvalid),.display_last(display_rlast),.display_rready(display_rready),
        .style_data(cnn_rdata),.style_resp(cnn_rresp),.style_rvalid(cnn_rvalid),.style_last(cnn_rlast),.style_rready(cnn_rready));
    wire awvalid,awready,wvalid,wready,bvalid,bready,arvalid,arready,rvalid,rlast,rready;
    wire [127:0] wdata,rdata;
    wire [1:0] bresp,rresp;
    frame_writer #(.WIDTH(PROC_WIDTH),.HEIGHT(PROC_HEIGHT),.BANK_STRIDE(30'd0),.ADDRESS_BASE(30'h00400000),.SESSION_TIMEOUT(500000000),.MAX_PAYLOAD_BYTES(UART_PAYLOAD_BYTES)) writer(.clk(ui_clk),.reset(reset_ui),.calibrated(calibrated),.rx_activity(rx_valid),
        .accelerator_busy(write_owner),.writer_idle(writer_idle),.source_invalidate(source_invalidate),
        .packet_valid(packet_valid),.packet_length(packet_length),.packet_crc(packet_crc),.bad_packet(bad_packet),
        .packet_consume(packet_consume),.packet_address(packet_address),.packet_data(packet_data),
        .reply_valid(reply_valid),.reply_ready(reply_ready),.reply_command(reply_command),.reply_status(reply_status),
        .reply_sequence(reply_sequence),.reply_frame(reply_frame),.reply_offset(reply_offset),
        .front_bank(front_bank),.commit_valid(writer_commit_valid),.commit_bank(writer_commit_bank),.commit_frame(writer_commit_frame),.commit_ack(writer_commit_ack),.commit_fail(writer_commit_fail),.selected_style(selected_style),.inference_cycles(last_inference_cycles),
        .awaddr(raw_awaddr),.awvalid(raw_awvalid),.awready(raw_awready),.wdata(raw_wdata),.wvalid(raw_wvalid),.wready(raw_wready),
        .bresp(bresp),.bvalid(raw_bvalid),.bready(raw_bready),.accepted_frames(accepted_frames),.rejected_packets(rejected_packets),.session_active(session_active));

    wire refresh_request,refresh_ack,refresh_window,fifo_reset,fifo_write,fifo_full,fifo_wr_busy,fifo_rd_busy,fifo_empty,fifo_read;
    wire [127:0] fifo_data;
    wire [15:0] fifo_pixel;
    wire [10:0] fifo_word_count;
    wire [31:0] read_errors,underflow_frames;
    frame_reader #(.WIDTH(PROC_WIDTH),.HEIGHT(PROC_HEIGHT)) reader(.clk(ui_clk),.reset(reset_ui),.calibrated(calibrated),.refresh_request(refresh_request),.refresh_ack(refresh_ack),
        .refresh_window(refresh_window),
        .commit_valid(commit_valid),.commit_bank(commit_bank),.commit_frame(commit_frame),.commit_ack(commit_ack),
        .front_bank(front_bank),.front_valid(front_valid),.front_frame(front_frame),
        .fifo_reset(fifo_reset),.fifo_data(fifo_data),.fifo_write(fifo_write),.fifo_full(fifo_full),
        // XPM wr_rst_busy already waits for rd_rst_busy assertion/deassertion
        // through its internal handshake. Do not resynchronize the same read
        // busy flop a second time into this domain (CDC-11 reconvergence).
        .fifo_wr_busy(fifo_wr_busy),.fifo_rd_busy(1'b0),.fifo_word_count(fifo_word_count),
        .araddr(display_araddr),.arvalid(display_arvalid),.arready(display_arready),.rdata(display_rdata),.rresp(display_rresp),.rvalid(display_rvalid),.rlast(display_rlast),.rready(display_rready),.read_errors(read_errors));
pixel_fifo_efx pixel_fifo(.rst(reset_ui || fifo_reset),.wr_clk(ui_clk),.rd_clk(pixel_clk),.din(fifo_data),
 .wr_en(fifo_write),.rd_en(fifo_read),.dout(fifo_pixel),.full(fifo_full),.empty(fifo_empty),
 .wr_rst_busy(fifo_wr_busy),.rd_rst_busy(fifo_rd_busy),.wr_data_count(fifo_word_count));
    wire hsync,vsync,de;
    wire [23:0] rgb;
    video_720p #(.H_FRONT(1760),.DISPLAY_WIDTH(PROC_WIDTH),.DISPLAY_HEIGHT(PROC_HEIGHT)) video(.clk(pixel_clk),.reset(reset_pixel),.fifo_pixel(fifo_pixel),.fifo_empty(fifo_empty),.fifo_busy(fifo_rd_busy),
        .fifo_read(fifo_read),.refresh_request(refresh_request),.refresh_ack(refresh_ack),.front_valid(front_valid),
        .refresh_window(refresh_window),
        .hsync(hsync),.vsync(vsync),.de(de),.rgb(rgb),.underflow_frames(underflow_frames));
tmds_efx display(.clk(pixel_clk),.reset(reset_pixel),.rgb(rgb),.de(de),.hsync(hsync),.vsync(vsync),
 .blue(tmds_tx_data0_TX_DATA),.green(tmds_tx_data1_TX_DATA),.red(tmds_tx_data2_TX_DATA),.clock_word(tmds_tx_clk_TX_DATA));
assign tmds_tx_clk_TX_RST=reset_pixel;assign tmds_tx_data0_TX_RST=reset_pixel;
assign tmds_tx_data1_TX_RST=reset_pixel;assign tmds_tx_data2_TX_RST=reset_pixel;
assign tmds_tx_clk_TX_OE=1'b1;assign tmds_tx_data0_TX_OE=1'b1;
assign tmds_tx_data1_TX_OE=1'b1;assign tmds_tx_data2_TX_OE=1'b1;
ddr3_top                 u_ddr3_top
(

.axi_clk                (ui_clk            ),
.core_clk               (ui_clk            ),
.sdram_clk              (sdram_clk           ),  
.rx_cal_clk             (rx_cal_clk          ),
.tx_cal_clk             (tx_cal_clk          ),
.tx_cal_clk_90edge      (tx_cal_clk_90edge   ),
.rstn                   (!ddr_reset             ),      
.pll_shift              (pll_shift           ),
.pll_shift_sel          (pll_shift_sel       ),
.pll_shift_ena          (pll_shift_ena       ),       
///////////////DDR BUS
.ddr_ck_hi              (ddr_ck_hi           ),
.ddr_ck_lo              (ddr_ck_lo           ),
.ddr_cke                (ddr_cke             ),    
.ddr_reset_n            (ddr_reset_n         ),
.ddr_cs_n               (ddr_cs_n            ),
.ddr_ras_n              (ddr_ras_n           ),
.ddr_cas_n              (ddr_cas_n           ),
.ddr_we_n               (ddr_we_n            ),     
.ddr_addr               (ddr_addr            ),
.ddr_ba                 (ddr_ba              ),

.ddr_dqs_oe             (ddr_dqs_oe          ),
.ddr_dqs_oe_n           (ddr_dqs_oe_n        ),
.ddr_dq_oe              (ddr_dq_oe           ),
.ddr_dqs_in_hi          (ddr_dqs_in_hi       ),
.ddr_dqs_in_lo          (ddr_dqs_in_lo       ),
.ddr_dq_in_hi           (ddr_dq_in_hi        ),
.ddr_dq_in_lo           (ddr_dq_in_lo        ),

.ddr_dqs_out_hi         (ddr_dqs_out_hi      ),
.ddr_dqs_out_lo         (ddr_dqs_out_lo      ),
.ddr_dq_out_hi          (ddr_dq_out_hi       ),
.ddr_dq_out_lo          (ddr_dq_out_lo       ),

.ddr_dm_hi              (ddr_dm_hi           ),
.ddr_dm_lo              (ddr_dm_lo           ),
.ddr_odt                (ddr_odt             ),

// Application interface ports
.app_sr_req                     (1'b0),
.app_ref_req                    (1'b0),
.app_zq_req                     (1'b0),
.app_sr_active                  (app_sr_active),
.app_ref_ack                    (app_ref_ack),
.app_zq_ack                     (app_zq_ack),

// Slave Interface Write Address Ports
 .s_axi_awid(4'd0),.s_axi_awaddr({2'b0,awaddr}),.s_axi_awlen(8'd0),.s_axi_awsize(3'd4),.s_axi_awburst(2'd1),
 .s_axi_awlock(1'b0),.s_axi_awcache(4'b0011),.s_axi_awprot(3'd0),.s_axi_awqos(4'd0),.s_axi_awvalid(awvalid),.s_axi_awready(awready),
 .s_axi_wdata(wdata),.s_axi_wstrb(16'hffff),.s_axi_wlast(1'b1),.s_axi_wvalid(wvalid),.s_axi_wready(wready),
 .s_axi_bid(),.s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),
 .s_axi_arid(4'd0),.s_axi_araddr({2'b0,araddr}),.s_axi_arlen(8'd15),.s_axi_arsize(3'd4),.s_axi_arburst(2'd1),
 .s_axi_arlock(1'b0),.s_axi_arcache(4'b0011),.s_axi_arprot(3'd0),.s_axi_arqos(4'd0),.s_axi_arvalid(arvalid),.s_axi_arready(arready),
 .s_axi_rid(),.s_axi_rdata(rdata),.s_axi_rresp(rresp),.s_axi_rlast(rlast),.s_axi_rvalid(rvalid),.s_axi_rready(rready),
 .cal_done(calibrated));
endmodule
