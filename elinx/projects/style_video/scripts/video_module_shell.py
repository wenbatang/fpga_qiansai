"""Board wiring for the public frame-memory and HDMI display modules."""


def encapsulate_video(board, *, color, contrast, contrast_level, wb, perf, reserve_cnn):
    # Camera extraction has already removed the RAW observer from this block.
    start=board.find('// Diagnostic measurements never gate')
    if start<0:start=board.index('style_cdc_counter stat_underflow(')
    end=board.index('style_platform_core #(',start)
    assert 'style_display_sink display_sink(' in board[start:end]
    board=board[:start]+board[end:]
    board=board.replace('style_platform_core #(', 'style_ddr_framebuffer #(',1)
    board=board.replace(')) platform(', ')) framebuffer(',1)
    start=board.index('// Existing licensed HDMI encoder,')
    end=board.index('reg [25:0] heartbeat;',start)
    old=board[start:end]
    camera_wb=''
    if wb:
        first=old.index('// All calibration arithmetic is in the 50 MHz camera domain.')
        last=old.index('// A held-valid FIFO transfer',first)
        camera_wb=old[first:last]
    first=old.index('assign tmds_tx_clk_TX_DATA=~tmds_clk;')
    pins=old[first:]
    # The pin assignments are the tail of the historical HDMI block.
    assert 'assign tmds_tx_data2_TX_RST=~pixel_rst_n;' in pins
    assert not any(name in pins for name in ('style_perf_overlay','style_wb_overlay','dvi_encoder'))
    perf_wires='wire [1023:0] perf_snapshot;\nwire perf_snapshot_valid;\n' if perf else ''
    wb_ports=".wb_state(wb_state),.wb_active_r(wb_active_r),.wb_active_b(wb_active_b)" if wb else ".wb_state(4'd0),.wb_active_r(11'd493),.wb_active_b(11'd504)"
    perf_ports='.perf_snapshot(perf_snapshot),.perf_snapshot_valid(perf_snapshot_valid)' if perf else ".perf_snapshot(1024'd0),.perf_snapshot_valid(1'b0)"
    instance='''// Separate board modules: camera_capture -> framebuffer -> hdmi_display.
@PERF_WIRES@
wire [12:0] display_fifo_level;
wire [9:0] tmds_data0,tmds_data1,tmds_data2,tmds_clk;
@CAMERA_WB@
style_hdmi_display #(
    .RESERVE_CNN(@RESERVE@),.COLOR_PROBE(@COLOR@),.CONTRAST_PROBE(@CONTRAST@),
    .CONTRAST_INITIAL_LEVEL(@LEVEL@),.WB_OVERLAY(@WB@),.PERF_OVERLAY(@PERF@)
) hdmi_display(
    .core_clk(core_clk),.core_rst_n(core_rst_n),.camera_clk(i_mipi_rx_pclk),.camera_rst_n(camera_rst_n),
    .pixel_clk(hdmi_tx_slow_clk),.pixel_rst_n(pixel_rst_n),.async_rst_n(w_arstn),
    .core_flush(display_flush),.core_front_valid(front_valid),.core_frame_id(front_id),.core_mode(mode),
    .capture_fps(capture_fps),.process_fps(process_fps),.bypass_active(bypass_active),
    .core_camera_frames(camera_frames_core),.core_drop_count(drop_count),.core_error_count(error_count),
    .s_rgb(display_rgb),.s_valid(display_valid),.s_ready(display_ready),
    .refresh_request(refresh_request),.refresh_ack(display_ack),.safe_window(safe_window),
    .raw_mean_valid(cfa_mean_valid),.raw_mean_data(cfa_mean_data),.key1_n(key1_n),
    @WB_PORTS@,
    @PERF_PORTS@,
    .video_rgb(video_rgb),.video_de(video_de),.video_hs(video_hs),.video_vs(video_vs),.video_x(video_x),.video_y(video_y),
    .tmds_data0(tmds_data0),.tmds_data1(tmds_data1),.tmds_data2(tmds_data2),.tmds_clk(tmds_clk),
    .underflows(underflows),.underflows_core(underflows_core),.fifo_level(display_fifo_level));
'''
    for name,value in dict(PERF_WIRES=perf_wires,CAMERA_WB=camera_wb,WB_PORTS=wb_ports,PERF_PORTS=perf_ports,
        RESERVE=int(reserve_cnn),COLOR=int(color),CONTRAST=int(contrast),LEVEL=contrast_level or 0,WB=int(wb),PERF=int(perf)).items():
        instance=instance.replace('@'+name+'@',str(value))
    board=board[:start]+instance+pins+board[end:]
    assert board.count(') hdmi_display(')==1 and board.count(')) framebuffer(')==1
    assert 'style_display_sink display_sink(' not in board and 'dvi_encoder hdmi_encoder(' not in board
    return board
