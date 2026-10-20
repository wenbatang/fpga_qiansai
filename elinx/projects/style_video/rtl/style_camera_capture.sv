// Portable acquisition boundary: decoded CSI RAW10 -> core-domain RGB stream.
// D-PHY/CSI IP, sensor I2C ownership and DDR remain in the board/platform shell.
// Reset all domains together; camera_rst_n/core_rst_n release synchronously.
module style_camera_capture #(
    parameter integer CAM_WIDTH=1920, CAM_HEIGHT=1080,
    parameter integer OUT_WIDTH=640, OUT_HEIGHT=480,
    parameter integer BAYER_PATTERN=0, QUEUE_DEPTH=256,
    parameter integer BLACK_LEVEL_A=0, BLACK_LEVEL_B=0,
    parameter integer BLACK_LEVEL_C=0, BLACK_LEVEL_D=0,
    parameter integer WB_GAIN_R_Q8=256, WB_GAIN_G_Q8=256, WB_GAIN_B_Q8=256,
    parameter integer DYNAMIC_WB=0, TONE_ENABLE=1, GAMMA_TENTHS=18,
    parameter integer FIFO_ADDR_BITS=10, ABORT_ADDR_BITS=4,
    parameter integer STATS_ENABLE=0,
    parameter integer ROI_X=896, ROI_Y=476, ROI_SIZE=128
)(
    input wire camera_clk, camera_rst_n, core_clk, core_rst_n, async_rst_n,
    // Camera domain: high-active frame/line, four RAW10 pixels low lane first.
    // No input ready: CSI cannot be stalled. s_valid is qualified by s_hs here.
    input wire s_vs, s_hs, s_valid,
    input wire [39:0] s_raw,
    // Camera-domain requests; DYNAMIC_WB latches gains at the next input SOF.
    input wire [10:0] wb_r_q8, wb_g_q8, wb_b_q8,
    // Core domain: one RGB888 pixel per accepted beat; all markers travel with it.
    output wire [23:0] m_rgb,
    output wire m_valid, input wire m_ready,
    output wire m_sof, m_eol, m_eof,
    output wire [31:0] m_frame_id,
    // Core-domain cancellation event. The receiver consumes every asserted beat.
    // Abort may precede or follow already queued pixels bearing the same ID.
    output wire m_abort, output wire [31:0] m_abort_frame_id,
    output wire [31:0] input_frames, drop_frames, error_frames,
    output wire abort_queue_fault,
    // Occupancy in the named domain (includes FIFO synchronizer/prefetch effects).
    output wire [FIFO_ADDR_BITS:0] camera_fifo_level, core_fifo_level,
    // Camera-domain optional RAW means BEFORE black correction/WB/tone.
    // Pulse, no ready: downstream diagnostics must consume or report overflow.
    output wire raw_mean_valid, output wire [39:0] raw_mean_data
);
    wire rgb_valid, rgb_ready, sof, eol, eof, abort_valid;
    wire [23:0] rgb_linear, rgb_tone;
    wire [31:0] frame_id, abort_id, camera_frames, camera_drops, camera_errors;
    style_camera_preprocess #(
        .CAM_WIDTH(CAM_WIDTH),.CAM_HEIGHT(CAM_HEIGHT),
        .OUT_WIDTH(OUT_WIDTH),.OUT_HEIGHT(OUT_HEIGHT),
        .BAYER_PATTERN(BAYER_PATTERN),.VS_ACTIVE(1),.QUEUE_DEPTH(QUEUE_DEPTH),
        .BLACK_LEVEL_A(BLACK_LEVEL_A),.BLACK_LEVEL_B(BLACK_LEVEL_B),
        .BLACK_LEVEL_C(BLACK_LEVEL_C),.BLACK_LEVEL_D(BLACK_LEVEL_D),
        .WB_GAIN_R_Q8(WB_GAIN_R_Q8),.WB_GAIN_G_Q8(WB_GAIN_G_Q8),.WB_GAIN_B_Q8(WB_GAIN_B_Q8),
        .DYNAMIC_WB(DYNAMIC_WB)
    ) preprocess(
        .clk(camera_clk),.rst_n(camera_rst_n),
        .s_vs(s_vs),.s_hs(s_hs),.s_valid(s_valid & s_hs),.s_raw(s_raw),
        .wb_r_q8(wb_r_q8),.wb_g_q8(wb_g_q8),.wb_b_q8(wb_b_q8),
        .m_valid(rgb_valid),.m_ready(rgb_ready),.m_rgb(rgb_linear),
        .m_sof(sof),.m_eol(eol),.m_eof(eof),.m_frame_id(frame_id),
        .m_abort(abort_valid),.m_abort_frame_id(abort_id),
        .input_frames(camera_frames),.drop_frames(camera_drops),.error_frames(camera_errors));
    style_rgb_gamma #(.ENABLE(TONE_ENABLE),.GAMMA_TENTHS(GAMMA_TENTHS)) tone(
        .s_rgb(rgb_linear),.m_rgb(rgb_tone));
    style_async_fifo #(.WIDTH(59),.ADDR_BITS(FIFO_ADDR_BITS)) camera_cdc(
        .wr_clk(camera_clk),.rd_clk(core_clk),.async_rst_n(async_rst_n),
        .s_data({frame_id,eof,eol,sof,rgb_tone}),.s_valid(rgb_valid),.s_ready(rgb_ready),
        .m_data({m_frame_id,m_eof,m_eol,m_sof,m_rgb}),.m_valid(m_valid),.m_ready(m_ready),
        .wr_level(camera_fifo_level),.rd_level(core_fifo_level));
    wire abort_ready;
    wire [ABORT_ADDR_BITS:0] abort_wr_level, abort_rd_level;
    style_async_fifo #(.WIDTH(32),.ADDR_BITS(ABORT_ADDR_BITS)) abort_cdc(
        .wr_clk(camera_clk),.rd_clk(core_clk),.async_rst_n(async_rst_n),
        .s_data(abort_id),.s_valid(abort_valid),.s_ready(abort_ready),
        .m_data(m_abort_frame_id),.m_valid(m_abort),.m_ready(1'b1),
        .wr_level(abort_wr_level),.rd_level(abort_rd_level));
    style_cdc_counter stat_camera(camera_clk,camera_rst_n,camera_frames,core_clk,core_rst_n,input_frames);
    style_cdc_counter stat_drops(camera_clk,camera_rst_n,camera_drops,core_clk,core_rst_n,drop_frames);
    style_cdc_counter stat_errors(camera_clk,camera_rst_n,camera_errors,core_clk,core_rst_n,error_frames);
    reg abort_fault;
    (* async_reg="true" *) reg [1:0] abort_fault_sync;
    always @(posedge camera_clk or negedge camera_rst_n)
        if(!camera_rst_n)abort_fault<=0;
        else if(abort_valid && !abort_ready)abort_fault<=1;
    always @(posedge core_clk or negedge core_rst_n)
        if(!core_rst_n)abort_fault_sync<=0;
        else abort_fault_sync<={abort_fault_sync[0],abort_fault};
    assign abort_queue_fault=abort_fault_sync[1];
    generate if(STATS_ENABLE) begin : raw_stats
        style_cfa_stats #(.CAM_WIDTH(CAM_WIDTH),.CAM_HEIGHT(CAM_HEIGHT),
            .ROI_X(ROI_X),.ROI_Y(ROI_Y),.ROI_SIZE(ROI_SIZE)) observer(
            .clk(camera_clk),.rst_n(camera_rst_n),.s_vs(s_vs),.s_hs(s_hs),
            .s_valid(s_valid & s_hs),.s_raw(s_raw),.mean_valid(raw_mean_valid),.mean_data(raw_mean_data));
    end else begin : no_raw_stats
        assign raw_mean_valid=1'b0;
        assign raw_mean_data=40'b0;
    end endgenerate
endmodule
