"""Replace the historical flat camera chain with its reusable acquisition port.

Called after profile selection so every physical camera setting is explicit.
The standalone initializer, CSI IP and display diagnostics retain their owners.
"""
import re


def encapsulate(board, *, bayer, black, gains, dynamic_wb, tone_enable, gamma, stats):
    start=board.index('wire cam_rgb_valid,cam_rgb_ready,cam_sof,cam_eol,cam_eof,cam_abort;')
    end=board.index('wire cal_done,app_sr_active,app_ref_ack,app_zq_ack;',start)
    old=board[start:end]
    # Fail closed if the source layout changes: never silently drop new logic.
    for name in ('camera_preprocess','camera_tone','camera_cdc','abort_cdc','stat_camera','stat_drops','stat_errors'):
        assert re.search(r'\b'+name+r'\s*\(',old),name+' missing from old capture chain'
    assert '.BAYER_PATTERN('+str(bayer)+')' in old
    parameters=[f'.BAYER_PATTERN({bayer})',f'.DYNAMIC_WB({int(dynamic_wb)})',
        f'.TONE_ENABLE({int(tone_enable)})',f'.GAMMA_TENTHS({gamma})',f'.STATS_ENABLE({int(stats)})']
    parameters += [f'.BLACK_LEVEL_{site}({value})' for site,value in zip('ABCD',black)]
    parameters += [f'.WB_GAIN_{site}_Q8({value})' for site,value in zip('RGB',gains)]
    requests=".wb_r_q8(wb_request_r),.wb_g_q8(11'd256),.wb_b_q8(wb_request_b)" if dynamic_wb else ".wb_r_q8(11'd256),.wb_g_q8(11'd256),.wb_b_q8(11'd256)"
    shell='''// Decoded CSI -> reusable acquisition module -> platform camera port.
wire core_cam_valid,core_cam_ready,core_cam_sof,core_cam_eol,core_cam_eof;
wire [23:0] core_cam_rgb;
wire [31:0] core_cam_id,core_abort_id;
wire core_abort_valid,camera_abort_fault;
wire [10:0] cam_wr_level,cam_rd_level;
wire [31:0] camera_frames_core,camera_drops_core,camera_errors_core;
wire cfa_mean_valid;
wire [39:0] cfa_mean_data;
style_camera_capture #(
    PARAMETERS
) camera_capture(
    .camera_clk(i_mipi_rx_pclk),.camera_rst_n(camera_rst_n),
    .core_clk(core_clk),.core_rst_n(core_rst_n),.async_rst_n(w_arstn),
    .s_vs(w_mipi_rx_vs),.s_hs(w_mipi_rx_hs),.s_valid(w_mipi_rx_de),.s_raw(w_mipi_rx_data[39:0]),
    REQUESTS,
    .m_rgb(core_cam_rgb),.m_valid(core_cam_valid),.m_ready(core_cam_ready),
    .m_sof(core_cam_sof),.m_eol(core_cam_eol),.m_eof(core_cam_eof),.m_frame_id(core_cam_id),
    .m_abort(core_abort_valid),.m_abort_frame_id(core_abort_id),
    .input_frames(camera_frames_core),.drop_frames(camera_drops_core),.error_frames(camera_errors_core),
    .abort_queue_fault(camera_abort_fault),.camera_fifo_level(cam_wr_level),.core_fifo_level(cam_rd_level),
    .raw_mean_valid(cfa_mean_valid),.raw_mean_data(cfa_mean_data));
'''.replace('PARAMETERS',',\n    '.join(parameters)).replace('REQUESTS',requests)
    board=board[:start]+shell+board[end:]
    board=board.replace('abort_fault_sync[1]','camera_abort_fault')
    if stats:
        board=board.replace('wire cfa_mean_valid,cfa_stats_ready,cfa_pixel_valid;','wire cfa_stats_ready,cfa_pixel_valid;',1)
        board=board.replace('wire [39:0] cfa_mean_data,cfa_pixel_data;','wire [39:0] cfa_pixel_data;',1)
        first=board.index('style_cfa_stats raw_cfa_stats(')
        last=board.index(');',first)+2
        board=board[:first]+board[last:]
    assert board.count(') camera_capture(')==1
    assert 'style_camera_preprocess #' not in board and 'style_cfa_stats raw_cfa_stats' not in board
    return board
