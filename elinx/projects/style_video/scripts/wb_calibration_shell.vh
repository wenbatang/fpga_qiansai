// All calibration arithmetic is in the 50 MHz camera domain.
wire [10:0] wb_request_r,wb_request_b,wb_active_r,wb_active_b;
wire [3:0] wb_state;
style_wb_calibrator wb_calibrator(.clk(i_mipi_rx_pclk),.rst_n(camera_rst_n),
    .key_cal_n(key2_n),.key_restore_n(key3_n),.s_vs(w_mipi_rx_vs),
    .mean_valid(cfa_mean_valid),.mean_data(cfa_mean_data),
    .request_r(wb_request_r),.request_b(wb_request_b),
    .active_r(wb_active_r),.active_b(wb_active_b),.state(wb_state));
// A held-valid FIFO transfer sends atomic tuples on change, including timeout
// status when the camera stops producing frames. No multi-bit direct CDC.
wire [25:0] wb_tuple={wb_state,wb_active_r,wb_active_b};
reg [25:0] wb_sent;
reg wb_sent_valid;
wire wb_status_ready,wb_pixel_valid;
wire [25:0] wb_pixel_data;
wire [2:0] wb_wr_level,wb_rd_level;
wire wb_changed=!wb_sent_valid || wb_tuple!=wb_sent;
// Hold a snapshot until accepted; new camera status can wait for the next entry.
reg [25:0] wb_pending;
reg wb_pending_valid;
always @(posedge i_mipi_rx_pclk or negedge camera_rst_n) begin
    if(!camera_rst_n) begin wb_sent<=0;wb_sent_valid<=0;wb_pending<=0;wb_pending_valid<=0;end
    else begin
        if(wb_pending_valid && wb_status_ready) begin
            wb_sent<=wb_pending;wb_sent_valid<=1;wb_pending_valid<=0;
        end else if(!wb_pending_valid && wb_changed) begin
            wb_pending<=wb_tuple;wb_pending_valid<=1;
        end
    end
end
style_async_fifo #(.WIDTH(26),.ADDR_BITS(2)) wb_status_cdc(
    .wr_clk(i_mipi_rx_pclk),.rd_clk(hdmi_tx_slow_clk),.async_rst_n(w_arstn),
    .s_data(wb_pending),.s_valid(wb_pending_valid),.s_ready(wb_status_ready),
    .m_data(wb_pixel_data),.m_valid(wb_pixel_valid),.m_ready(1'b1),
    .wr_level(wb_wr_level),.rd_level(wb_rd_level));
reg [25:0] wb_latest,wb_overlay;
always @(posedge hdmi_tx_slow_clk or negedge pixel_rst_n) begin
    if(!pixel_rst_n) begin wb_latest<={4'd0,11'd493,11'd504};wb_overlay<={4'd0,11'd493,11'd504};end
    else begin
        if(wb_pixel_valid) wb_latest<=wb_pixel_data;
        if(video_x==0 && video_y==0) wb_overlay<=wb_latest;
    end
end
wire [23:0] wb_rgb;
style_wb_overlay wb_ui(.x(video_x),.y(video_y),.input_rgb(contrast_rgb),
    .state(wb_overlay[25:22]),.gain_r(wb_overlay[21:11]),.gain_b(wb_overlay[10:0]),.rgb(wb_rgb));
