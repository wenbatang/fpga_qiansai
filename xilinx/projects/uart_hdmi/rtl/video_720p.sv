// Standard 1280x720@60: 1650x750 totals; +HS/+VS; 74.25 MHz pixel clock.
module video_720p #(
    parameter integer H_ACTIVE=1280, H_FRONT=110, H_SYNC=40, H_BACK=220,
    parameter integer V_ACTIVE=720, V_FRONT=5, V_SYNC=5, V_BACK=20
)(input wire clk, reset,
  input wire [15:0] fifo_pixel, input wire fifo_empty, fifo_busy,
  output wire fifo_read,
  output reg refresh_request, input wire refresh_ack, front_valid,
  output reg refresh_window,
  output reg hsync, vsync, de, output reg [23:0] rgb,
  output reg [31:0] underflow_frames);
    localparam integer H_TOTAL=H_ACTIVE+H_FRONT+H_SYNC+H_BACK;
    localparam integer V_TOTAL=V_ACTIVE+V_FRONT+V_SYNC+V_BACK;
    localparam integer H_START=H_SYNC+H_BACK, V_START=V_SYNC+V_BACK;
    reg [11:0] h,v;
    reg frame_bad;
    (* ASYNC_REG="TRUE" *) reg [1:0] ack_sync, valid_sync;
    wire active=h>=H_START && h<H_START+H_ACTIVE && v>=V_START && v<V_START+V_ACTIVE;
    wire ready=ack_sync[1]==refresh_request && valid_sync[1] && !fifo_busy;
    wire missing=active && valid_sync[1] && (!ready || fifo_empty);
    assign fifo_read=active && ready && !frame_bad && !fifo_empty;
    wire [23:0] expanded={fifo_pixel[15:11],fifo_pixel[15:13],
                          fifo_pixel[10:5],fifo_pixel[10:9],fifo_pixel[4:0],fifo_pixel[4:2]};
    always @(posedge clk) begin
        if (reset) begin ack_sync<=0; valid_sync<=0; end
        else begin ack_sync<={ack_sync[0],refresh_ack}; valid_sync<={valid_sync[0],front_valid}; end
    end
    always @(posedge clk) begin
        if (reset) begin
            h<=0; v<=0; frame_bad<=0; refresh_request<=0;
            refresh_window<=0;
            hsync<=0; vsync<=0; de<=0; rgb<=0; underflow_frames<=0;
        end else begin
            // Registered single-bit CDC signal. Close one full line before
            // active video so synchronizer latency cannot permit a late swap.
            refresh_window<=v<V_START-1;
            if (h==H_TOTAL-1) begin h<=0; if (v==V_TOTAL-1) v<=0; else v<=v+1; end
            else h<=h+1;
            if (h==0 && v==0) begin
                if (ack_sync[1]==refresh_request) refresh_request<=~refresh_request;
                frame_bad<=0;
            end
            if (missing && !frame_bad) begin frame_bad<=1; underflow_frames<=underflow_frames+1; end
            hsync<=h<H_SYNC; vsync<=v<V_SYNC; de<=active;
            if (!active || !valid_sync[1]) rgb<=24'd0;
            else if (frame_bad || missing) rgb<=24'hFF00FF;
            else rgb<=expanded;
        end
    end
endmodule
