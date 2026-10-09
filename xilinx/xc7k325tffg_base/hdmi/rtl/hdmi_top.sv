module hdmi_top(
    input   logic       sys_clk     ,
    input   logic       sys_rst_n   ,
    output  logic       tmds_clk_p  ,
    output  logic       tmds_clk_n  ,
    output  logic [2:0] tmds_data_p ,
    output  logic [2:0] tmds_data_n ,

    output  logic       tmds_out_en
);

logic       pixel_clk       ;
logic       pixel_clk5x     ;
logic       clk_locked      ;

logic       rst_n           ;
assign      rst_n = sys_rst_n & clk_locked;

wire  [10:0]  pixel_xpos_w;
wire  [10:0]  pixel_ypos_w;
wire  [23:0]  pixel_data_w;

wire          video_hs;
wire          video_vs;
wire          video_de;
wire  [23:0]  video_rgb;

clk_wiz_0 u_pll
(
    // Clock out ports
    .clk_out1(pixel_clk),     // output clk_out1
    .clk_out2(pixel_clk5x),     // output clk_out2
    // Status and control signals
    .reset(~sys_rst_n), // input reset
    .locked(clk_locked),       // output locked
   // Clock in ports
    .clk_in1(sys_clk)      // input clk_in1
);

//视频显示驱动模块
hdmi_driver  u_video_driver(
    .pixel_clk      ( pixel_clk ),
    .sys_rst_n      ( rst_n ),

    .video_hs       ( video_hs ),
    .video_vs       ( video_vs ),
    .video_de       ( video_de ),
    .video_rgb      ( video_rgb ),
	.data_req		(),

    .pixel_xpos     ( pixel_xpos_w ),
    .pixel_ypos     ( pixel_ypos_w ),
	.pixel_data     ( pixel_data_w )
);

//视频显示模块
hdmi_disp  u_video_display(
    .pixel_clk      (pixel_clk),
    .sys_rst_n      (rst_n),

    .pixel_xpos     (pixel_xpos_w),
    .pixel_ypos     (pixel_ypos_w),
    .pixel_data     (pixel_data_w)
    );

//以下为HDMI发送模块
hdmi_rgb2dvi u_rgb2dvi_0(
    .pixel_clk      (pixel_clk),
    .pixel_clk5x    (pixel_clk5x),
    .rst_n          (rst_n),

    .pixel_rgb      (video_rgb),
    .pixel_den      (video_de),
    .hdmi_hsync     (video_hs),
    .hdmi_vsync     (video_vs),

    .tmds_clk_p     (tmds_clk_p),
    .tmds_clk_n     (tmds_clk_n),
    .tmds_data_p    (tmds_data_p),
    .tmds_data_n    (tmds_data_n),
    .tmds_out_en    (tmds_out_en)
    );


endmodule