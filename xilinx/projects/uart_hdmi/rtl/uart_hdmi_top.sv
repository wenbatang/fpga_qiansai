module uart_hdmi_top #(
    parameter integer UART_BAUD=115200,
    parameter integer UART_PAYLOAD_BYTES=1024
)(input wire sys_clk, sys_rst_n, uart_rx, output wire uart_tx,
  output wire tmds_clk_p,tmds_clk_n,
  output wire [2:0] tmds_data_p,tmds_data_n, output wire tmds_out_en,
  inout wire [31:0] ddr3_dq, inout wire [3:0] ddr3_dqs_n,ddr3_dqs_p,
  output wire [14:0] ddr3_addr, output wire [2:0] ddr3_ba,
  output wire ddr3_ras_n,ddr3_cas_n,ddr3_we_n,ddr3_reset_n,
  output wire [0:0] ddr3_ck_p,ddr3_ck_n,ddr3_cke,ddr3_cs_n,ddr3_odt,
  output wire [3:0] ddr3_dm);
    wire ddr_sys_clk,reference_clk,ddr_locked,pixel_clk,serial_clk,video_locked;
    wire ui_clk,ui_reset,calibrated,reset_ui,reset_pixel;
    uart_ddr_clocks ddr_clocks(.clk_in1(sys_clk),.resetn(sys_rst_n),
        .clk_out1(ddr_sys_clk),.locked(ddr_locked));
    assign reference_clk=ddr_sys_clk;
    // Cascade from MIG UI, avoiding unknown phase between parallel PLL/MMCMs.
    video_clocks hdmi_clocks(.reference_100mhz(ui_clk),.reset(!sys_rst_n || !ddr_locked || ui_reset),
        .pixel_clk(pixel_clk),.serial_clk(serial_clk),.locked(video_locked));
    reset_sync rst_ui(.clk(ui_clk),.async_reset(ui_reset || !sys_rst_n || !ddr_locked || !calibrated),.reset(reset_ui));
    // Synchronize each independent reset source before combining. This avoids
    // combinational logic on the CDC path into a reset synchronizer.
    wire reset_pixel_sys,reset_pixel_lock,reset_pixel_calib,reset_pixel_ui;
    reset_sync rst_pixel_sys(.clk(pixel_clk),.async_reset(!sys_rst_n),.reset(reset_pixel_sys));
    reset_sync rst_pixel_lock(.clk(pixel_clk),.async_reset(!video_locked),.reset(reset_pixel_lock));
    reset_sync rst_pixel_calib(.clk(pixel_clk),.async_reset(!calibrated),.reset(reset_pixel_calib));
    reset_sync rst_pixel_ui(.clk(pixel_clk),.async_reset(ui_reset),.reset(reset_pixel_ui));
    assign reset_pixel=reset_pixel_sys || reset_pixel_lock || reset_pixel_calib || reset_pixel_ui;
    assign tmds_out_en=sys_rst_n && video_locked;

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
    packet_rx #(.MAX_BYTES(UART_PAYLOAD_BYTES+24),.TIMEOUT_CYCLES(100000000)) packets(.clk(ui_clk),.reset(reset_ui),.byte_data(rx_data),.byte_valid(rx_valid),
        .framing_error(rx_error),.consume(packet_consume),.read_address(packet_address),.read_data(packet_data),
        .packet_valid(packet_valid),.packet_length(packet_length),.packet_crc(packet_crc),
        .bad_packet(bad_packet),.error_count(packet_errors));
    wire reply_valid,reply_ready;
    wire [7:0] reply_command,reply_status;
    wire [15:0] reply_sequence;
    wire [31:0] reply_frame,reply_offset;
    packet_reply replies(.clk(ui_clk),.reset(reset_ui),.valid(reply_valid),.ready(reply_ready),
        .command(reply_command),.status(reply_status),.sequence_id(reply_sequence),
        .frame_id(reply_frame),.accepted_offset(reply_offset),.tx_data(tx_data),.tx_valid(tx_valid),.tx_ready(tx_ready));

    wire front_bank,front_valid,commit_valid,commit_bank,commit_ack,session_active;
    wire [31:0] front_frame,commit_frame,accepted_frames,rejected_packets;
    wire [29:0] awaddr,araddr;
    wire awvalid,awready,wvalid,wready,bvalid,bready,arvalid,arready,rvalid,rlast,rready;
    wire [127:0] wdata,rdata;
    wire [1:0] bresp,rresp;
    frame_writer #(.SESSION_TIMEOUT(500000000),.MAX_PAYLOAD_BYTES(UART_PAYLOAD_BYTES)) writer(.clk(ui_clk),.reset(reset_ui),.calibrated(calibrated),.rx_activity(rx_valid),
        .packet_valid(packet_valid),.packet_length(packet_length),.packet_crc(packet_crc),.bad_packet(bad_packet),
        .packet_consume(packet_consume),.packet_address(packet_address),.packet_data(packet_data),
        .reply_valid(reply_valid),.reply_ready(reply_ready),.reply_command(reply_command),.reply_status(reply_status),
        .reply_sequence(reply_sequence),.reply_frame(reply_frame),.reply_offset(reply_offset),
        .front_bank(front_bank),.commit_valid(commit_valid),.commit_bank(commit_bank),.commit_frame(commit_frame),.commit_ack(commit_ack),
        .awaddr(awaddr),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wvalid(wvalid),.wready(wready),
        .bresp(bresp),.bvalid(bvalid),.bready(bready),.accepted_frames(accepted_frames),.rejected_packets(rejected_packets),.session_active(session_active));

    wire refresh_request,refresh_ack,refresh_window,fifo_reset,fifo_write,fifo_full,fifo_wr_busy,fifo_rd_busy,fifo_empty,fifo_read;
    wire [127:0] fifo_data;
    wire [15:0] fifo_pixel;
    wire [10:0] fifo_word_count;
    wire [31:0] read_errors,underflow_frames;
    frame_reader reader(.clk(ui_clk),.reset(reset_ui),.calibrated(calibrated),.refresh_request(refresh_request),.refresh_ack(refresh_ack),
        .refresh_window(refresh_window),
        .commit_valid(commit_valid),.commit_bank(commit_bank),.commit_frame(commit_frame),.commit_ack(commit_ack),
        .front_bank(front_bank),.front_valid(front_valid),.front_frame(front_frame),
        .fifo_reset(fifo_reset),.fifo_data(fifo_data),.fifo_write(fifo_write),.fifo_full(fifo_full),
        // XPM wr_rst_busy already waits for rd_rst_busy assertion/deassertion
        // through its internal handshake. Do not resynchronize the same read
        // busy flop a second time into this domain (CDC-11 reconvergence).
        .fifo_wr_busy(fifo_wr_busy),.fifo_rd_busy(1'b0),.fifo_word_count(fifo_word_count),
        .araddr(araddr),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rresp(rresp),.rvalid(rvalid),.rlast(rlast),.rready(rready),.read_errors(read_errors));
    xpm_fifo_async #(
        .CDC_SYNC_STAGES(2),.DOUT_RESET_VALUE("0"),.ECC_MODE("no_ecc"),
        .FIFO_MEMORY_TYPE("block"),.FIFO_READ_LATENCY(0),.FIFO_WRITE_DEPTH(1024),
        .FULL_RESET_VALUE(0),.PROG_EMPTY_THRESH(16),.PROG_FULL_THRESH(992),
        .RD_DATA_COUNT_WIDTH(14),.READ_DATA_WIDTH(16),.READ_MODE("fwft"),
        .RELATED_CLOCKS(0),.SIM_ASSERT_CHK(1),.USE_ADV_FEATURES("0707"),
        .WAKEUP_TIME(0),.WRITE_DATA_WIDTH(128),.WR_DATA_COUNT_WIDTH(11)
    ) pixel_fifo (
        .rst(reset_ui || fifo_reset),.wr_clk(ui_clk),.rd_clk(pixel_clk),.din(fifo_data),
        .wr_en(fifo_write && !fifo_wr_busy),.rd_en(fifo_read && !fifo_rd_busy),
        .dout(fifo_pixel),.full(fifo_full),.empty(fifo_empty),
        .wr_rst_busy(fifo_wr_busy),.rd_rst_busy(fifo_rd_busy),.wr_data_count(fifo_word_count),.rd_data_count(),
        .almost_empty(),.almost_full(),.data_valid(),.overflow(),.underflow(),.prog_empty(),.prog_full(),.wr_ack(),
        .dbiterr(),.sbiterr(),.injectdbiterr(1'b0),.injectsbiterr(1'b0),.sleep(1'b0));
    wire hsync,vsync,de;
    wire [23:0] rgb;
    video_720p video(.clk(pixel_clk),.reset(reset_pixel),.fifo_pixel(fifo_pixel),.fifo_empty(fifo_empty),.fifo_busy(fifo_rd_busy),
        .fifo_read(fifo_read),.refresh_request(refresh_request),.refresh_ack(refresh_ack),.front_valid(front_valid),
        .refresh_window(refresh_window),
        .hsync(hsync),.vsync(vsync),.de(de),.rgb(rgb),.underflow_frames(underflow_frames));
    tmds_output display(.pixel_clk(pixel_clk),.serial_clk(serial_clk),.reset(reset_pixel),.rgb(rgb),.de(de),.hsync(hsync),.vsync(vsync),
        .tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),.tmds_data_p(tmds_data_p),.tmds_data_n(tmds_data_n));
    uart_mig memory (
        .ddr3_dq(ddr3_dq),.ddr3_dqs_n(ddr3_dqs_n),.ddr3_dqs_p(ddr3_dqs_p),.ddr3_addr(ddr3_addr),.ddr3_ba(ddr3_ba),
        .ddr3_ras_n(ddr3_ras_n),.ddr3_cas_n(ddr3_cas_n),.ddr3_we_n(ddr3_we_n),.ddr3_reset_n(ddr3_reset_n),
        .ddr3_ck_p(ddr3_ck_p),.ddr3_ck_n(ddr3_ck_n),.ddr3_cke(ddr3_cke),.ddr3_cs_n(ddr3_cs_n),.ddr3_dm(ddr3_dm),.ddr3_odt(ddr3_odt),
        .sys_clk_i(ddr_sys_clk),.clk_ref_i(reference_clk),.sys_rst(sys_rst_n && ddr_locked),
        .ui_clk(ui_clk),.ui_clk_sync_rst(ui_reset),.init_calib_complete(calibrated),.mmcm_locked(),.aresetn(!reset_ui),
        .app_sr_req(1'b0),.app_ref_req(1'b0),.app_zq_req(1'b0),.app_sr_active(),.app_ref_ack(),.app_zq_ack(),.device_temp(),
        .s_axi_awid(4'd0),.s_axi_awaddr(awaddr),.s_axi_awlen(8'd0),.s_axi_awsize(3'd4),.s_axi_awburst(2'd1),
        .s_axi_awlock(1'b0),.s_axi_awcache(4'b0011),.s_axi_awprot(3'd0),.s_axi_awqos(4'd0),.s_axi_awvalid(awvalid),.s_axi_awready(awready),
        .s_axi_wdata(wdata),.s_axi_wstrb(16'hFFFF),.s_axi_wlast(1'b1),.s_axi_wvalid(wvalid),.s_axi_wready(wready),
        .s_axi_bid(),.s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),
        .s_axi_arid(4'd0),.s_axi_araddr(araddr),.s_axi_arlen(8'd15),.s_axi_arsize(3'd4),.s_axi_arburst(2'd1),
        .s_axi_arlock(1'b0),.s_axi_arcache(4'b0011),.s_axi_arprot(3'd0),.s_axi_arqos(4'd0),.s_axi_arvalid(arvalid),.s_axi_arready(arready),
        .s_axi_rid(),.s_axi_rdata(rdata),.s_axi_rresp(rresp),.s_axi_rlast(rlast),.s_axi_rvalid(rvalid),.s_axi_rready(rready));
endmodule
