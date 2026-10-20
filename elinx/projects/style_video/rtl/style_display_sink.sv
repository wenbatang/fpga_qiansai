// Input tokens contain 1280*480 RGB888 pixels: each line is original then
// result, without blanking tokens. A disabled pane still consumes its tokens.
module style_display_sink #(
    parameter integer H_ACTIVE=1280, H_FRONT=110, H_SYNC=40, H_BACK=220,
    parameter integer V_ACTIVE=720, V_FRONT=5, V_SYNC=5, V_BACK=20,
    parameter integer IMAGE_WIDTH=640, IMAGE_HEIGHT=480, IMAGE_Y=120,
    parameter integer SAFE_END=100, FIFO_ADDR_BITS=12, ENABLE_OSD=1
)(
    input wire core_clk, core_rst_n, pixel_clk, pixel_rst_n,
    input wire core_flush, core_front_valid,
    input wire [31:0] core_frame_id,
    input wire [1:0] core_mode,
    input wire [15:0] capture_fps, process_fps,
    input wire [31:0] core_camera_frames, core_drop_count, core_error_count,
    input wire bypass_active,
    input wire [23:0] s_rgb,
    input wire s_valid,
    output wire s_ready,
    output reg refresh_request,
    input wire refresh_ack,
    output wire safe_window,
    output reg [23:0] video_rgb,
    output wire video_de, video_hs, video_vs,
    output wire [15:0] video_x, video_y,
    output reg [31:0] underflow_count,
    // Read-only write-domain FIFO occupancy for passive diagnostics.
    output wire [FIFO_ADDR_BITS:0] monitor_fifo_level
);
    localparam integer IMAGE_END=IMAGE_Y+IMAGE_HEIGHT;
    wire frame_start;
    style_video_timing #(
        .H_ACTIVE(H_ACTIVE),.H_FRONT(H_FRONT),.H_SYNC(H_SYNC),.H_BACK(H_BACK),
        .V_ACTIVE(V_ACTIVE),.V_FRONT(V_FRONT),.V_SYNC(V_SYNC),.V_BACK(V_BACK),
        .SAFE_START(IMAGE_END),.SAFE_END(SAFE_END)
    ) timing (
        .pixel_clk(pixel_clk),.pixel_rst_n(pixel_rst_n),.x(video_x),.y(video_y),
        .de(video_de),.hs(video_hs),.vs(video_vs),.frame_start(frame_start),.safe_window(safe_window)
    );

    // A one-cycle core_flush is expanded to 16 core clocks. FIFO synchronizes
    // deassertion independently in both domains; both pointers reset together.
    reg [4:0] flush_count;
    always @(posedge core_clk or negedge core_rst_n) begin
        if (!core_rst_n) flush_count<=16;
        else if (core_flush) flush_count<=16;
        else if (flush_count!=0) flush_count<=flush_count-1'b1;
    end
    wire flush_active=core_flush || flush_count!=0;
    wire fifo_rst_n=core_rst_n && pixel_rst_n && !flush_active;
    wire [23:0] fifo_rgb;
    wire fifo_valid, fifo_ready;
    wire [FIFO_ADDR_BITS:0] wr_level, rd_level;
    assign monitor_fifo_level=wr_level;
    style_async_fifo #(.WIDTH(24),.ADDR_BITS(FIFO_ADDR_BITS)) fifo (
        .wr_clk(core_clk),.rd_clk(pixel_clk),.async_rst_n(fifo_rst_n),
        .s_data(s_rgb),.s_valid(s_valid),.s_ready(s_ready),
        .m_data(fifo_rgb),.m_valid(fifo_valid),.m_ready(fifo_ready),
        .wr_level(wr_level),.rd_level(rd_level)
    );

    // Bundled-data handshake: snapshot the configuration when core asserts
    // ACK. The snapshot cannot change again until the next request/ACK cycle.
    // Two ACK synchronizer stages then qualify its sampling in pixel domain.
    reg ack_last, bundle_ack;
    reg cfg_valid, cfg_bypass;
    reg [31:0] cfg_frame;
    reg [1:0] cfg_mode;
    reg [15:0] cfg_capture_fps, cfg_process_fps;
    reg [31:0] cfg_camera_frames, cfg_drops, cfg_errors;
    always @(posedge core_clk or negedge core_rst_n) begin
        if (!core_rst_n) begin
            ack_last<=0; bundle_ack<=0; cfg_valid<=0; cfg_bypass<=0; cfg_frame<=0; cfg_mode<=0;
            cfg_capture_fps<=0; cfg_process_fps<=0;
            cfg_camera_frames<=0; cfg_drops<=0; cfg_errors<=0;
        end else begin
            ack_last<=refresh_ack;
            // Register the notification alongside the snapshot. Synchronizing
            // raw ACK directly could outrun snapshot capture with slow core_clk.
            bundle_ack<=refresh_ack;
            if (refresh_ack && !ack_last) begin
                cfg_valid<=core_front_valid; cfg_frame<=core_frame_id; cfg_mode<=core_mode;
                cfg_capture_fps<=capture_fps; cfg_process_fps<=process_fps; cfg_bypass<=bypass_active;
                cfg_camera_frames<=core_camera_frames; cfg_drops<=core_drop_count; cfg_errors<=core_error_count;
            end
        end
    end
    (* async_reg="true" *) reg ack_p1, ack_p2, flush_p1, flush_p2;
    always @(posedge pixel_clk or negedge pixel_rst_n) begin
        if (!pixel_rst_n) begin ack_p1<=0; ack_p2<=0; flush_p1<=1; flush_p2<=1; end
        else begin
            ack_p1<=bundle_ack; ack_p2<=ack_p1;
            flush_p1<=flush_active; flush_p2<=flush_p1;
        end
    end
    reg front_valid, front_bypass;
    reg [31:0] front_frame;
    reg [1:0] front_mode;
    reg [15:0] front_capture_fps, front_process_fps;
    reg [31:0] front_camera_frames, front_drops, front_errors, front_underflows;
    reg frame_poisoned;
    wire image_area=video_de && video_x<2*IMAGE_WIDTH && video_y>=IMAGE_Y && video_y<IMAGE_END;
    wire refresh_at_end=(video_x==0 && video_y==IMAGE_END);
    wire accept_refresh=refresh_request && ack_p2 && safe_window;
    assign fifo_ready=image_area && front_valid && !frame_poisoned && !flush_p2 && !refresh_request;
    always @(posedge pixel_clk or negedge pixel_rst_n) begin
        if (!pixel_rst_n) begin
            refresh_request<=1; front_valid<=0; front_frame<=0; front_mode<=0;
            front_capture_fps<=0; front_process_fps<=0; front_bypass<=0;
            front_camera_frames<=0; front_drops<=0; front_errors<=0; front_underflows<=0;
            frame_poisoned<=0; underflow_count<=0;
        end else begin
            if (refresh_at_end) refresh_request<=1;
            if (accept_refresh) begin
                refresh_request<=0;
                front_valid<=cfg_valid; front_frame<=cfg_frame; front_mode<=cfg_mode;
                front_capture_fps<=cfg_capture_fps; front_process_fps<=cfg_process_fps;
                front_bypass<=cfg_bypass; frame_poisoned<=0;
                front_camera_frames<=cfg_camera_frames; front_drops<=cfg_drops; front_errors<=cfg_errors;
                front_underflows<=underflow_count;
            end
            if (flush_p2) frame_poisoned<=0;
            else if (image_area && front_valid && !frame_poisoned &&
                     !refresh_request && !fifo_valid) begin
                frame_poisoned<=1;
                underflow_count<=underflow_count+1'b1;
            end
        end
    end
    wire osd_hit;
    wire [23:0] osd_rgb;
    style_osd #(.IMAGE_WIDTH(IMAGE_WIDTH),.IMAGE_Y(IMAGE_Y),.IMAGE_HEIGHT(IMAGE_HEIGHT)) osd (
        .x(video_x),.y(video_y),.capture_fps(front_capture_fps),.process_fps(front_process_fps),
        .frame_id(front_frame),.bypass_active(front_bypass),.hit(osd_hit),.rgb(osd_rgb),
        .camera_frames(front_camera_frames),.drop_count(front_drops),.error_count(front_errors),.underflow_count(front_underflows)
    );
    always @* begin
        video_rgb=0;
        if (video_de) begin
            if (image_area && front_valid && !flush_p2 && !refresh_request) begin
                if (frame_poisoned || !fifo_valid) video_rgb=24'hFF00FF;
                else if ((front_mode==1 && video_x>=IMAGE_WIDTH) ||
                         (front_mode==2 && video_x<IMAGE_WIDTH)) video_rgb=0;
                else video_rgb=fifo_rgb;
            end else if (!image_area && ENABLE_OSD && osd_hit) video_rgb=osd_rgb;
        end
    end
endmodule
