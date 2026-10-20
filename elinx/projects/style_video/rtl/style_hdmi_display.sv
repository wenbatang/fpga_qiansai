// Display boundary: paired RGB tokens -> FIFO/timing/OSD/diagnostics -> TMDS.
// RESERVE_CNN=1 guarantees a black right image pane after every overlay/error.
// Both panes' input tokens are still consumed to preserve the DDR stream order.
// ENCODE_TMDS=0 is for portable simulation; the Efinity board always uses 1.
module style_hdmi_display #(
    parameter integer H_ACTIVE=1280,H_FRONT=110,H_SYNC=40,H_BACK=220,
    parameter integer V_ACTIVE=720,V_FRONT=5,V_SYNC=5,V_BACK=20,
    parameter integer IMAGE_WIDTH=640,IMAGE_HEIGHT=480,IMAGE_Y=120,SAFE_END=100,
    parameter integer FIFO_ADDR_BITS=12,ENABLE_OSD=1,
    parameter integer RESERVE_CNN=1,ENCODE_TMDS=1,
    parameter integer COLOR_PROBE=0,CONTRAST_PROBE=0,CONTRAST_INITIAL_LEVEL=0,
    parameter integer WB_OVERLAY=0,PERF_OVERLAY=0
)(
    input wire core_clk,core_rst_n,camera_clk,camera_rst_n,pixel_clk,pixel_rst_n,async_rst_n,
    input wire core_flush,core_front_valid,
    input wire [31:0] core_frame_id,
    input wire [1:0] core_mode,
    input wire [15:0] capture_fps,process_fps,
    input wire [31:0] core_camera_frames,core_drop_count,core_error_count,
    input wire bypass_active,
    // Core domain, one row contains IMAGE_WIDTH original then result pixels.
    input wire [23:0] s_rgb,input wire s_valid,output wire s_ready,
    output wire refresh_request,input wire refresh_ack,output wire safe_window,
    // Optional camera-domain diagnostic pulses and stable WB status tuple.
    input wire raw_mean_valid,input wire [39:0] raw_mean_data,
    input wire key1_n,input wire [3:0] wb_state,
    input wire [10:0] wb_active_r,wb_active_b,
    input wire [1023:0] perf_snapshot,input wire perf_snapshot_valid,
    // Pixel-domain video taps; TMDS words feed the board's existing serializer.
    output wire [23:0] video_rgb,output wire video_de,video_hs,video_vs,
    output wire [15:0] video_x,video_y,
    output wire [9:0] tmds_data0,tmds_data1,tmds_data2,tmds_clk,
    output wire [31:0] underflows,underflows_core,
    output wire [FIFO_ADDR_BITS:0] fifo_level
);
    wire [23:0] sink_rgb,color_rgb,contrast_rgb,wb_rgb,perf_rgb;
    style_display_sink #(
        .H_ACTIVE(H_ACTIVE),.H_FRONT(H_FRONT),.H_SYNC(H_SYNC),.H_BACK(H_BACK),
        .V_ACTIVE(V_ACTIVE),.V_FRONT(V_FRONT),.V_SYNC(V_SYNC),.V_BACK(V_BACK),
        .IMAGE_WIDTH(IMAGE_WIDTH),.IMAGE_HEIGHT(IMAGE_HEIGHT),.IMAGE_Y(IMAGE_Y),
        .SAFE_END(SAFE_END),.FIFO_ADDR_BITS(FIFO_ADDR_BITS),.ENABLE_OSD(ENABLE_OSD)
    ) sink(
        .core_clk(core_clk),.core_rst_n(core_rst_n),.pixel_clk(pixel_clk),.pixel_rst_n(pixel_rst_n),
        .core_flush(core_flush),.core_front_valid(core_front_valid),.core_frame_id(core_frame_id),
        .core_mode(RESERVE_CNN ? 2'd1 : core_mode),
        .capture_fps(capture_fps),.process_fps(process_fps),.bypass_active(bypass_active),
        .core_camera_frames(core_camera_frames),.core_drop_count(core_drop_count),.core_error_count(core_error_count),
        .s_rgb(s_rgb),.s_valid(s_valid),.s_ready(s_ready),
        .refresh_request(refresh_request),.refresh_ack(refresh_ack),.safe_window(safe_window),
        .video_rgb(sink_rgb),.video_de(video_de),.video_hs(video_hs),.video_vs(video_vs),
        .video_x(video_x),.video_y(video_y),.underflow_count(underflows),.monitor_fifo_level(fifo_level));
    style_cdc_counter stat_underflow(pixel_clk,pixel_rst_n,underflows,core_clk,core_rst_n,underflows_core);

    wire [39:0] cfa_overlay;
    wire cfa_overlay_valid;
    generate if(COLOR_PROBE || CONTRAST_PROBE) begin : raw_diagnostics
        wire stats_ready,pixel_valid;
        wire [39:0] pixel_data;
        wire [2:0] wr_level,rd_level;
        style_async_fifo #(.WIDTH(40),.ADDR_BITS(2)) color_stats_cdc(
            .wr_clk(camera_clk),.rd_clk(pixel_clk),.async_rst_n(async_rst_n),
            .s_data(raw_mean_data),.s_valid(raw_mean_valid),.s_ready(stats_ready),
            .m_data(pixel_data),.m_valid(pixel_valid),.m_ready(1'b1),.wr_level(wr_level),.rd_level(rd_level));
        reg overflow;
        (* async_reg="true" *) reg [1:0] overflow_sync;
        reg [39:0] latest,overlay;
        reg seen,overlay_valid;
        always @(posedge camera_clk or negedge camera_rst_n)
            if(!camera_rst_n)overflow<=0;
            else if(raw_mean_valid && !stats_ready)overflow<=1;
        always @(posedge pixel_clk or negedge pixel_rst_n) begin
            if(!pixel_rst_n) begin overflow_sync<=0;latest<=0;overlay<=0;seen<=0;overlay_valid<=0;end
            else begin
                overflow_sync<={overflow_sync[0],overflow};
                if(pixel_valid)begin latest<=pixel_data;seen<=1;end
                if(video_x==0 && video_y==640)begin overlay<=latest;overlay_valid<=seen && !overflow_sync[1];end
            end
        end
        assign cfa_overlay=overlay;
        assign cfa_overlay_valid=overlay_valid;
    end else begin : no_raw_diagnostics
        assign cfa_overlay=0;assign cfa_overlay_valid=0;
    end endgenerate
    generate if(COLOR_PROBE) begin : color_diagnostic
        style_color_probe_overlay ui(.x(video_x),.y(video_y),.input_rgb(sink_rgb),
            .cfa_means(cfa_overlay),.sample_valid(cfa_overlay_valid),.rgb(color_rgb));
    end else begin : no_color_diagnostic
        assign color_rgb=sink_rgb;
    end endgenerate
    generate if(CONTRAST_PROBE) begin : contrast_diagnostic
        wire [2:0] level;
        style_contrast_probe #(.INITIAL_LEVEL(CONTRAST_INITIAL_LEVEL)) ui(
            .clk(pixel_clk),.rst_n(pixel_rst_n),.key1_n(key1_n),.x(video_x),.y(video_y),
            .input_rgb(color_rgb),.cfa_means(cfa_overlay),.sample_valid(cfa_overlay_valid),.rgb(contrast_rgb),.level(level));
    end else begin : no_contrast_diagnostic
        assign contrast_rgb=color_rgb;
    end endgenerate
    generate if(WB_OVERLAY) begin : white_balance_diagnostic
        wire [25:0] tuple={wb_state,wb_active_r,wb_active_b};
        reg [25:0] sent,pending;
        reg sent_valid,pending_valid;
        wire status_ready,pixel_valid;
        wire [25:0] pixel_data;
        wire [2:0] wr_level,rd_level;
        wire changed=!sent_valid || tuple!=sent;
        always @(posedge camera_clk or negedge camera_rst_n) begin
            if(!camera_rst_n)begin sent<=0;sent_valid<=0;pending<=0;pending_valid<=0;end
            else if(pending_valid && status_ready)begin sent<=pending;sent_valid<=1;pending_valid<=0;end
            else if(!pending_valid && changed)begin pending<=tuple;pending_valid<=1;end
        end
        style_async_fifo #(.WIDTH(26),.ADDR_BITS(2)) wb_status_cdc(
            .wr_clk(camera_clk),.rd_clk(pixel_clk),.async_rst_n(async_rst_n),
            .s_data(pending),.s_valid(pending_valid),.s_ready(status_ready),
            .m_data(pixel_data),.m_valid(pixel_valid),.m_ready(1'b1),.wr_level(wr_level),.rd_level(rd_level));
        reg [25:0] latest,overlay;
        always @(posedge pixel_clk or negedge pixel_rst_n) begin
            if(!pixel_rst_n)begin latest<={4'd0,11'd493,11'd504};overlay<={4'd0,11'd493,11'd504};end
            else begin
                if(pixel_valid)latest<=pixel_data;
                if(video_x==0 && video_y==0)overlay<=latest;
            end
        end
        style_wb_overlay ui(.x(video_x),.y(video_y),.input_rgb(contrast_rgb),
            .state(overlay[25:22]),.gain_r(overlay[21:11]),.gain_b(overlay[10:0]),.rgb(wb_rgb));
    end else begin : no_white_balance_diagnostic
        assign wb_rgb=contrast_rgb;
    end endgenerate
    generate if(PERF_OVERLAY) begin : performance_diagnostic
        style_perf_overlay ui(.core_clk(core_clk),.core_rst_n(core_rst_n),
            .pixel_clk(pixel_clk),.pixel_rst_n(pixel_rst_n),.async_rst_n(async_rst_n),
            .snapshot(perf_snapshot),.snapshot_valid(perf_snapshot_valid),.x(video_x),.y(video_y),
            .input_rgb(wb_rgb),.rgb(perf_rgb));
    end else begin : no_performance_diagnostic
        assign perf_rgb=wb_rgb;
    end endgenerate
    // Final mask is AFTER all diagnostics and underflow poison, so a reserved
    // right image cannot accidentally display stale COPY pixels or pink error.
    wire reserved_right=RESERVE_CNN && video_de && video_x>=IMAGE_WIDTH &&
        video_x<2*IMAGE_WIDTH && video_y>=IMAGE_Y && video_y<IMAGE_Y+IMAGE_HEIGHT;
    assign video_rgb=reserved_right ? 24'b0 : perf_rgb;
    generate if(ENCODE_TMDS) begin : hdmi
        dvi_encoder encoder(.pixelclk(pixel_clk),.rst_p(~pixel_rst_n),
            .i_rdata(video_rgb[23:16]),.i_gdata(video_rgb[15:8]),.i_bdata(video_rgb[7:0]),
            .i_de(video_de),.i_hs(video_hs),.i_vs(video_vs),.video_format(2'b00),.video_VIC(7'd4),
            .audio_L(24'b0),.audio_R(24'b0),.audio_valid(1'b0),.audio_N(20'd6144),.audio_CTS(20'd74250),
            .audio_sample_frequency(4'b0010),.audio_word_length(4'b1011),
            .tmds_data0(tmds_data0),.tmds_data1(tmds_data1),.tmds_data2(tmds_data2),.tmds_clk(tmds_clk));
    end else begin : no_encoder
        assign tmds_data0=0;assign tmds_data1=0;assign tmds_data2=0;assign tmds_clk=0;
    end endgenerate
endmodule
