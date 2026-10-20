// Coordinates are active-area based: (0,0) is the first visible pixel.
// Default 74.25 MHz / (1650*750) = 60 Hz, positive sync polarity.
module style_video_timing #(
    parameter integer H_ACTIVE=1280, H_FRONT=110, H_SYNC=40, H_BACK=220,
    parameter integer V_ACTIVE=720, V_FRONT=5, V_SYNC=5, V_BACK=20,
    parameter integer SAFE_START=600, SAFE_END=100
)(
    input wire pixel_clk, pixel_rst_n,
    output wire [15:0] x, y,
    output wire de, hs, vs, frame_start, safe_window
);
    localparam integer H_TOTAL=H_ACTIVE+H_FRONT+H_SYNC+H_BACK;
    localparam integer V_TOTAL=V_ACTIVE+V_FRONT+V_SYNC+V_BACK;
    reg [15:0] h_count, v_count;
    always @(posedge pixel_clk or negedge pixel_rst_n) begin
        if (!pixel_rst_n) begin h_count<=0; v_count<=0; end
        else if (h_count==H_TOTAL-1) begin
            h_count<=0;
            if (v_count==V_TOTAL-1) v_count<=0;
            else v_count<=v_count+1'b1;
        end else h_count<=h_count+1'b1;
    end
    assign x=h_count;
    assign y=v_count;
    assign de=pixel_rst_n && h_count<H_ACTIVE && v_count<V_ACTIVE;
    assign hs=pixel_rst_n && h_count>=H_ACTIVE+H_FRONT && h_count<H_ACTIVE+H_FRONT+H_SYNC;
    assign vs=pixel_rst_n && v_count>=V_ACTIVE+V_FRONT && v_count<V_ACTIVE+V_FRONT+V_SYNC;
    assign frame_start=pixel_rst_n && h_count==0 && v_count==0;
    assign safe_window=pixel_rst_n && (v_count>=SAFE_START || v_count<SAFE_END);
endmodule
