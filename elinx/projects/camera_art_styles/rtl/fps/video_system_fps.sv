// Camera/DDR/CNN/control/display subsystem. Board PHY/Sapphire live in top.
module video_system_fps #(parameter WIDTH=1280,HEIGHT=720)(
 input wire clk,fast_clk,reset,pixel_clk,pixel_reset,calibrated,
 input wire[15:0] paddr,input wire psel,penable,pwrite,input wire[31:0] pwdata,
 output wire[31:0] prdata,output wire pready,pslverror,irq,
 input wire[3:0] keys_n,input wire scl_in,sda_in,output wire scl_release,sda_release,sensor_reset_n,
 input wire cam_vs,cam_hs,cam_valid,input wire[39:0] cam_raw,input wire cam_error,
 output wire[29:0] awaddr,araddr,output wire awvalid,input wire awready,
 output wire[127:0] wdata,output wire wvalid,input wire wready,
 input wire[1:0] bresp,input wire bvalid,output wire bready,
 output wire arvalid,input wire arready,input wire[127:0] rdata,
 input wire[1:0] rresp,input wire rvalid,rlast,output wire rready,
 output wire[23:0] display_rgb,output wire hsync,vsync,de,
 output wire[31:0] diag_capture_frames,diag_inference_frames,diag_capture_errors,diag_engine_cycles,
 output wire[3:0] diag_status,output wire[287:0] view_fields);
 wire capture_enable,overlay_enable,start,cfg_valid,cfg_ready,weights_valid;
 wire[15:0] cfg_address;wire[31:0] cfg_data;
 wire[1:0] loaded_style,requested_style,key_style;
 wire key_event,busy,completed,failed,raw_mode,engine_raw;
 wire[127:0] source_stats,output_stats;
 wire[31:0] job_frames;reg[31:0] neural_frames;reg front_raw;
 wire[31:0] captured_frames,skipped_frames,inference_frames,engine_cycles,capture_errors;
 wire[31:0] latest_frame,engine_frame;
 wire latest_valid;
 style_keys_view keys(.clk(clk),.reset(reset),.keys_n(keys_n),.event_valid(key_event),.event_style(key_style),.raw_mode(raw_mode));
 reg[31:0] error_previous;
 always @(posedge clk)if(reset)error_previous<=0;else error_previous<=capture_errors;
 video_control_apb_fps control(.cfg_ready(cfg_ready),.clk(clk),.reset(reset),.paddr(paddr),.psel(psel),.penable(penable),.pwrite(pwrite),.pwdata(pwdata),
  .prdata(prdata),.pready(pready),.pslverror(pslverror),.busy(busy),.source_valid(latest_valid),
  .source_frame(latest_frame),.engine_cycles(engine_cycles),.inference_frames(inference_frames),
  .capture_frames(captured_frames),.dropped_frames(skipped_frames+capture_errors),.completed(completed),.failed(failed),
  .camera_fault(capture_errors!=error_previous),.key_event(key_event),.key_style(key_style),.scl_in(scl_in),.sda_in(sda_in),
  .capture_enable(capture_enable),.sensor_reset_n(sensor_reset_n),.overlay_enable(overlay_enable),
  .scl_release(scl_release),.sda_release(sda_release),.start(start),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data),
  .weights_valid(weights_valid),.loaded_style(loaded_style),.requested_style(requested_style),.irq(irq));
 wire[31:0] camera_pixels;wire camera_pixel_valid,camera_start,camera_end,camera_bad;
 camera_bayer_720 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) reduce(.clk(clk),.reset(reset),.vs(cam_vs),.hs(cam_hs),.valid(cam_valid),
  .raw(cam_raw),.pattern(2'd0),.packet_error(cam_error),.pixels(camera_pixels),.pixel_valid(camera_pixel_valid),
  .frame_start(camera_start),.frame_end(camera_end),.frame_bad(camera_bad));
 video_rgb_stats #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) input_stats(
  .clk(clk),.reset(reset),.frame_start(camera_start),.frame_end(camera_end),.frame_bad(camera_bad),
  .pixel_valid(camera_pixel_valid),.pixels(camera_pixels),.stats(source_stats));
 wire capture_fifo_full,capture_fifo_empty,capture_fifo_write,capture_fifo_read;
 wire[178:0] capture_fifo_data,capture_fifo_out;wire[31:0] camera_overflows;
 camera_pack_720 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) packer(.clk(clk),.reset(reset),.enable(capture_enable),
  .frame_start(camera_start),.frame_end(camera_end),.frame_bad(camera_bad),.pixel_valid(camera_pixel_valid),.pixels(camera_pixels),
  .fifo_full(capture_fifo_full),.fifo_write(capture_fifo_write),.fifo_data(capture_fifo_data),.overflow_frames(camera_overflows));
 efx_fifo_wrapper #(.FAMILY("TITANIUM"),.SYNC_CLK(1),.MODE("FWFT"),.DEPTH(512),.DATA_WIDTH(179),.PIPELINE_REG(1),.OUTPUT_REG(0))
  capture_fifo(.a_rst_i(reset),.a_wr_rst_i(1'b0),.a_rd_rst_i(1'b0),.clk_i(clk),.wr_clk_i(1'b0),.rd_clk_i(1'b0),
  .wr_en_i(capture_fifo_write),.rd_en_i(capture_fifo_read),.wdata(capture_fifo_data),.rdata(capture_fifo_out),
  .full_o(capture_fifo_full),.empty_o(capture_fifo_empty),.almost_full_o(),.prog_full_o(),.overflow_o(),.wr_ack_o(),.datacount_o(),
  .almost_empty_o(),.prog_empty_o(),.underflow_o(),.rd_valid_o(),.rd_datacount_o(),.wr_datacount_o(),.rst_busy());
 wire allocate,allocation_ack,publish,abort_capture,claim,claim_ack,release_source;
 wire[1:0] capture_bank,engine_bank;wire[31:0] capture_frame;
 source_frame_pool pool(.clk(clk),.reset(reset),.allocate(allocate),.allocation_ack(allocation_ack),.capture_bank(capture_bank),
  .publish(publish),.abort_capture(abort_capture),.capture_frame(capture_frame),.claim(claim),.claim_ack(claim_ack),
  .release_source(release_source),.engine_bank(engine_bank),.engine_frame(engine_frame),.latest_valid(latest_valid),.latest_frame(latest_frame),
  .captured_frames(captured_frames),.skipped_frames(skipped_frames),.capturing(),.locked());
 wire[29:0] raw_awaddr,cnn_awaddr,cnn_araddr,display_araddr;
 wire[127:0] raw_wdata,cnn_wdata,cnn_rdata,display_rdata;
 wire raw_awvalid,raw_awready,raw_wvalid,raw_wready,raw_bvalid,raw_bready;
 wire cnn_awvalid,cnn_awready,cnn_wvalid,cnn_wready,cnn_bvalid,cnn_bready;
 wire cnn_arvalid,cnn_arready,cnn_rvalid,cnn_rlast,cnn_rready;
 wire display_arvalid,display_arready,display_rvalid,display_rlast,display_rready;
 wire[1:0] raw_bresp,cnn_bresp,cnn_rresp,display_rresp;
 camera_frame_writer_720 #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) writer(.clk(clk),.reset(reset),.fifo_data(capture_fifo_out),.fifo_empty(capture_fifo_empty),
  .fifo_read(capture_fifo_read),.allocate(allocate),.allocation_ack(allocation_ack),.capture_bank(capture_bank),
  .publish(publish),.abort_capture(abort_capture),.capture_frame(capture_frame),.error_frames(capture_errors),
  .awaddr(raw_awaddr),.awvalid(raw_awvalid),.awready(raw_awready),.wdata(raw_wdata),.wvalid(raw_wvalid),.wready(raw_wready),
  .bresp(raw_bresp),.bvalid(raw_bvalid),.bready(raw_bready));
 axi_write_pair_fps writes(.clk(clk),.reset(reset),.a_addr(raw_awaddr),.b_addr(cnn_awaddr),.a_awvalid(raw_awvalid),.b_awvalid(cnn_awvalid),
  .a_awready(raw_awready),.b_awready(cnn_awready),.a_data(raw_wdata),.b_data(cnn_wdata),.a_wvalid(raw_wvalid),.b_wvalid(cnn_wvalid),
  .a_wready(raw_wready),.b_wready(cnn_wready),.a_bvalid(raw_bvalid),.b_bvalid(cnn_bvalid),.a_bready(raw_bready),.b_bready(cnn_bready),
  .a_resp(raw_bresp),.b_resp(cnn_bresp),.awaddr(awaddr),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wvalid(wvalid),.wready(wready),
  .bresp(bresp),.bvalid(bvalid),.bready(bready));
 wire engine_start,engine_done,engine_error,engine_busy;
 wire commit_valid,commit_ack,front_valid,commit_raw,displayed;wire[1:0]commit_bank,front_bank,output_bank;
 wire[31:0] commit_frame,front_frame;
 video_job_control_fps jobs(.clk(clk),.reset(reset),.start(start),.raw_mode(raw_mode),.output_bank(output_bank),.commit_raw(commit_raw),.displayed(displayed),.busy(busy),.claim(claim),.claim_ack(claim_ack),.source_frame(engine_frame),
  .release_source(release_source),.engine_start(engine_start),.engine_done(engine_done),.engine_error(engine_error),
  .commit_valid(commit_valid),.commit_bank(commit_bank),.commit_frame(commit_frame),.commit_ack(commit_ack),.front_bank(front_bank),
  .front_valid(front_valid),.completed(completed),.failed(failed),.inference_frames(job_frames));
 fps_tile_engine_3bank #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) engine(.clk(clk),.fast_clk(fast_clk),.cfg_ready(cfg_ready),.reset(reset),.start(engine_start),.style(loaded_style),.raw_mode(raw_mode),.raw_active(engine_raw),.image_stats(output_stats),
  .output_bank(output_bank),.source_base(30'h00400000+engine_bank*30'h00200000),.cfg_valid(cfg_valid),.cfg_address(cfg_address),.cfg_data(cfg_data),
  .busy(engine_busy),.done(engine_done),.error(engine_error),.cycles(engine_cycles),
  .araddr(cnn_araddr),.arvalid(cnn_arvalid),.arready(cnn_arready),.rdata(cnn_rdata),.rresp(cnn_rresp),.rvalid(cnn_rvalid),.rlast(cnn_rlast),.rready(cnn_rready),
  .awaddr(cnn_awaddr),.awvalid(cnn_awvalid),.awready(cnn_awready),.wdata(cnn_wdata),.wvalid(cnn_wvalid),.wready(cnn_wready),
  .bresp(cnn_bresp),.bvalid(cnn_bvalid),.bready(cnn_bready));
 style_read_arbiter read_bus(.clk(clk),.reset(reset),.display_addr(display_araddr),.display_valid(display_arvalid),.display_ready(display_arready),
  .style_addr(cnn_araddr),.style_valid(cnn_arvalid),.style_ready(cnn_arready),.araddr(araddr),.arvalid(arvalid),.arready(arready),
  .rdata(rdata),.rresp(rresp),.rvalid(rvalid),.rlast(rlast),.rready(rready),
  .display_data(display_rdata),.display_resp(display_rresp),.display_rvalid(display_rvalid),.display_last(display_rlast),.display_rready(display_rready),
  .style_data(cnn_rdata),.style_resp(cnn_rresp),.style_rvalid(cnn_rvalid),.style_last(cnn_rlast),.style_rready(cnn_rready));
 wire refresh_request,refresh_ack,refresh_window,fifo_reset,fifo_write,fifo_full,fifo_wr_busy,fifo_rd_busy,fifo_empty,fifo_read;
 wire[127:0] fifo_data;wire[15:0] fifo_pixel;wire[10:0] fifo_word_count;wire[31:0] read_errors,underflow_frames;
 frame_reader_fps #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.FIFO_WORDS(512)) reader(.clk(clk),.reset(reset),.calibrated(calibrated),.refresh_request(refresh_request),.refresh_ack(refresh_ack),
  .refresh_window(refresh_window),.commit_valid(commit_valid),.commit_bank(commit_bank),.commit_frame(commit_frame),.commit_ack(commit_ack),
  .front_bank(front_bank),.front_valid(front_valid),.front_frame(front_frame),.fifo_reset(fifo_reset),.fifo_data(fifo_data),.fifo_write(fifo_write),
  .fifo_full(fifo_full),.fifo_wr_busy(fifo_wr_busy),.fifo_rd_busy(fifo_rd_busy),.fifo_word_count(fifo_word_count),
  .araddr(display_araddr),.arvalid(display_arvalid),.arready(display_arready),.rdata(display_rdata),.rresp(display_rresp),.rvalid(display_rvalid),
  .rlast(display_rlast),.rready(display_rready),.read_errors(read_errors));
 pixel_fifo_fps pixel_fifo(.rst(reset || fifo_reset),.wr_clk(clk),.rd_clk(pixel_clk),.din(fifo_data),.wr_en(fifo_write),.rd_en(fifo_read),
  .dout(fifo_pixel),.full(fifo_full),.empty(fifo_empty),.wr_rst_busy(fifo_wr_busy),.rd_rst_busy(fifo_rd_busy),.wr_data_count(fifo_word_count));
 wire[23:0] rgb;wire[11:0] x,y;
 video_raster60 #(.H_FRONT(110),.DISPLAY_WIDTH(WIDTH),.DISPLAY_HEIGHT(HEIGHT)) video(.clk(pixel_clk),.reset(pixel_reset),
  .fifo_pixel(fifo_pixel),.fifo_empty(fifo_empty),.fifo_busy(fifo_rd_busy),.fifo_read(fifo_read),.refresh_request(refresh_request),.refresh_ack(refresh_ack),
  .front_valid(front_valid),.refresh_window(refresh_window),.hsync(hsync),.vsync(vsync),.de(de),.rgb(rgb),.x(x),.y(y),.underflow_frames(underflow_frames));
 wire[7:0] capture_fps,inference_fps;
 fps_snapshot fps(.clk(clk),.reset(reset),.captured(captured_frames),.inferred(inference_frames),.pixel_clk(pixel_clk),.pixel_reset(pixel_reset),
  .vblank(vsync),.capture_fps(capture_fps),.inference_fps(inference_fps));
 (* async_reg="true",syn_srlstyle="registers" *) reg[1:0] overlay_sync;
 always @(posedge pixel_clk)if(pixel_reset)overlay_sync<=0;else overlay_sync<={overlay_sync[0],overlay_enable};
 fps_overlay60 overlay(.x(x),.y(y),.capture_fps(capture_fps),.inference_fps(inference_fps),.enable(overlay_sync[1]),.de(de),.rgb(rgb),.out_rgb(display_rgb));
// Only completed neural jobs count toward Ixx. Raw copying never does.
 always @(posedge clk)begin
  if(reset)begin neural_frames<=0;front_raw<=1;end
  else begin
   if(engine_done && !engine_raw)neural_frames<=neural_frames+1'b1;
   if(commit_ack)front_raw<=commit_raw;
  end
 end
 assign inference_frames=neural_frames;
 assign view_fields={source_stats,output_stats,{25'd0,front_raw,requested_style,loaded_style,engine_raw,raw_mode}};
// Observations only; no new ready, enable, reset, or command driver.
 assign diag_capture_frames=captured_frames;
 assign diag_inference_frames=inference_frames;
 assign diag_capture_errors=capture_errors;
 assign diag_engine_cycles=engine_cycles;
 assign diag_status={front_valid,weights_valid,busy,latest_valid};
endmodule
