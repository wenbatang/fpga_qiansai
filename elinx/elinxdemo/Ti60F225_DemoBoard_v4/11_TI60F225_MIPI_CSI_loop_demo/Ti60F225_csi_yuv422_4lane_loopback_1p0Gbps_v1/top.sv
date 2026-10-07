
// synopsys translate_off
`timescale 1 ns / 1 ps													
// synopsys translate_on

module top #(   //csi2 example design
    parameter PIXEL_BIT  = 16,
    parameter PACK_BIT   = 64,
    parameter HSA		 = 8,  //minimum value is pixel cnt value, eg: RGB888 - 2
    parameter HBP		 = 8,   //minimum value is pixel cnt value, eg: RGB888 - 2
    parameter HFP		 = 5000,
    parameter HACT_CNT	 = 1920,//2960
    parameter VSA		 = 1,
    parameter VBP		 = 1,
    parameter VFP		 = 100,
    parameter VACT_CNT	 = 1080,//1182
    parameter DATATYPE = 6'h1E     //24 - RGB888
)(
input 			mipi_clk,	//100MHz
input 			reset_n,  //sw5
output [3:0] 	O_LED,
input			pixel_clk,	//50Mhz
input           pll_locked,
output          pll_rstn,

input 			mipi_dphy_rx_clk_LP_P_IN,
input			mipi_dphy_rx_clk_LP_N_IN,
output			mipi_dphy_rx_clk_HS_TERM,
output			mipi_dphy_rx_clk_HS_ENA,
input 			mipi_dphy_rx_clk_CLKOUT,

input	[7:0]	mipi_dphy_rx_data0_HS_IN,
input			mipi_dphy_rx_data0_LP_P_IN,
input			mipi_dphy_rx_data0_LP_N_IN,
output          mipi_dphy_rx_data0_RST,
output			mipi_dphy_rx_data0_HS_TERM,
output			mipi_dphy_rx_data0_HS_ENA,
output 			mipi_dphy_rx_data0_FIFO_RD,
input 			mipi_dphy_rx_data0_FIFO_EMPTY,
output 			mipi_dphy_rx_data0_DLY_RST,
output 			mipi_dphy_rx_data0_DLY_INC,
output 			mipi_dphy_rx_data0_DLY_ENA,

input	[7:0]	mipi_dphy_rx_data1_HS_IN,
input			mipi_dphy_rx_data1_LP_P_IN,
input			mipi_dphy_rx_data1_LP_N_IN,
output          mipi_dphy_rx_data1_RST,
output			mipi_dphy_rx_data1_HS_TERM,
output			mipi_dphy_rx_data1_HS_ENA,
output 			mipi_dphy_rx_data1_FIFO_RD,
input 			mipi_dphy_rx_data1_FIFO_EMPTY,
output 			mipi_dphy_rx_data1_DLY_RST,
output 			mipi_dphy_rx_data1_DLY_INC,
output 			mipi_dphy_rx_data1_DLY_ENA,

input	[7:0]	mipi_dphy_rx_data2_HS_IN,
input			mipi_dphy_rx_data2_LP_P_IN,
input			mipi_dphy_rx_data2_LP_N_IN,
output          mipi_dphy_rx_data2_RST,
output			mipi_dphy_rx_data2_HS_TERM,
output			mipi_dphy_rx_data2_HS_ENA,
output 			mipi_dphy_rx_data2_FIFO_RD,
input 			mipi_dphy_rx_data2_FIFO_EMPTY,
output 			mipi_dphy_rx_data2_DLY_RST,
output 			mipi_dphy_rx_data2_DLY_INC,
output 			mipi_dphy_rx_data2_DLY_ENA,

input	[7:0]	mipi_dphy_rx_data3_HS_IN,
input			mipi_dphy_rx_data3_LP_P_IN,
input			mipi_dphy_rx_data3_LP_N_IN,
output          mipi_dphy_rx_data3_RST,
output			mipi_dphy_rx_data3_HS_TERM,
output			mipi_dphy_rx_data3_HS_ENA,
output 			mipi_dphy_rx_data3_FIFO_RD,
input 			mipi_dphy_rx_data3_FIFO_EMPTY,
output 			mipi_dphy_rx_data3_DLY_RST,
output 			mipi_dphy_rx_data3_DLY_INC,
output 			mipi_dphy_rx_data3_DLY_ENA,

input           mipi_dphy_tx_SLOWCLK,
output 			mipi_dphy_tx_HS_enable_C,
output  [7:0]   mipi_dphy_tx_clk_HS_OUT,
output          mipi_dphy_tx_clk_RST,
output			mipi_dphy_tx_clk_LP_P_OE,
output			mipi_dphy_tx_clk_LP_P_OUT,
output			mipi_dphy_tx_clk_LP_N_OE,
output			mipi_dphy_tx_clk_LP_N_OUT,

output			mipi_dphy_tx_data0_HS_OE,
output	[7:0]	mipi_dphy_tx_data0_HS_OUT,
output          mipi_dphy_tx_data0_RST,
output			mipi_dphy_tx_data0_LP_N_OE,
output			mipi_dphy_tx_data0_LP_N_OUT,
output			mipi_dphy_tx_data0_LP_P_OE,
output			mipi_dphy_tx_data0_LP_P_OUT,

output			mipi_dphy_tx_data1_HS_OE,
output	[7:0]	mipi_dphy_tx_data1_HS_OUT,
output          mipi_dphy_tx_data1_RST,
output			mipi_dphy_tx_data1_LP_N_OE,
output			mipi_dphy_tx_data1_LP_N_OUT,
output			mipi_dphy_tx_data1_LP_P_OE,
output			mipi_dphy_tx_data1_LP_P_OUT,

output			mipi_dphy_tx_data2_HS_OE,
output	[7:0]	mipi_dphy_tx_data2_HS_OUT,
output          mipi_dphy_tx_data2_RST,
output			mipi_dphy_tx_data2_LP_N_OE,
output			mipi_dphy_tx_data2_LP_N_OUT,
output			mipi_dphy_tx_data2_LP_P_OE,
output			mipi_dphy_tx_data2_LP_P_OUT,

output			mipi_dphy_tx_data3_HS_OE,
output	[7:0]	mipi_dphy_tx_data3_HS_OUT,
output          mipi_dphy_tx_data3_RST,
output			mipi_dphy_tx_data3_LP_N_OE,
output			mipi_dphy_tx_data3_LP_N_OUT,
output			mipi_dphy_tx_data3_LP_P_OE,
output			mipi_dphy_tx_data3_LP_P_OUT
);
//============================================================================================= 
//localparm
//=============================================================================================
localparam FIFO_WIDTH = 13;
localparam PIXEL_FIFO_DEPTH = 2048;  //set to a power of 2 value that is bigger than HACT_CNT
localparam CLOCK_FREQ_MHZ = 100;
//============================================================================================= 
//signal
//=============================================================================================
// rx signal
logic rx_out_valid_1P;
logic rx_out_hs_1P;
logic mipi_clk_reset_n;
logic mipi_dphy_rx_reset_byte_HS_n;
logic reset_pixel_n;
logic mipi_dphy_tx_reset_byte_HS_n;
logic [26:0] count_led;
logic [5:0] datatype;
logic [15:0] word_count;
logic [FIFO_WIDTH-1:0] r_x_active_1P, r_y_active_1P;

logic [FIFO_WIDTH-1:0] video_x;
logic [FIFO_WIDTH-1:0] video_y;
logic video_valid;
logic video_de;
logic video_hs;
logic video_vs;
logic tx_out_valid;
logic tx_out_hs;
logic tx_out_vs;
logic [PACK_BIT-1:0] tx_out_data;
logic [FIFO_WIDTH-1:0] pg_x;
logic [FIFO_WIDTH-1:0] pg_y;
logic pg_valid;
logic pg_de;
logic pg_hs;
logic pg_vs;
logic [PIXEL_BIT-1:0] pg_data;
//============================================================================================= 
//reset processing
//=============================================================================================

assign pll_rstn = 1'b1;

always @ (posedge mipi_dphy_rx_clk_CLKOUT or negedge mipi_dphy_rx_reset_byte_HS_n) begin
    if (~mipi_dphy_rx_reset_byte_HS_n) 
        count_led <= 'h0;
    else 
        count_led <= count_led + 1'd1;
end

assign	mipi_dphy_tx_clk_RST	= 1'b0;
assign	mipi_dphy_tx_data0_RST	= 1'b0;
assign  mipi_dphy_rx_data0_RST   = 1'b0;
assign	mipi_dphy_tx_data1_RST	= 1'b0;
assign  mipi_dphy_rx_data1_RST   = 1'b0;
assign	mipi_dphy_tx_data2_RST	= 1'b0;
assign  mipi_dphy_rx_data2_RST   = 1'b0;
assign	mipi_dphy_tx_data3_RST	= 1'b0;
assign  mipi_dphy_rx_data3_RST   = 1'b0;



reset
#(
	.IN_RST_ACTIVE	("LOW"),
	.OUT_RST_ACTIVE	("LOW"),
	.CYCLE			(3)
)
inst_clk_rst
(
	.i_arst	(reset_n),
	.i_clk	(mipi_clk),
	.o_srst	(mipi_clk_reset_n)
);

reset
#(
	.IN_RST_ACTIVE	("LOW"),
	.OUT_RST_ACTIVE	("LOW"),
	.CYCLE			(3)
)
inst_rx_byteclk_rst
(
	.i_arst	(reset_n),
	.i_clk	(mipi_dphy_rx_clk_CLKOUT),
	.o_srst	(mipi_dphy_rx_reset_byte_HS_n)
);

reset
#(
	.IN_RST_ACTIVE	("LOW"),
	.OUT_RST_ACTIVE	("LOW"),
	.CYCLE			(3)
)
inst_tx_byteclk_rst
(
	.i_arst	(reset_n),
	.i_clk	(mipi_dphy_tx_SLOWCLK),
	.o_srst	(mipi_dphy_tx_reset_byte_HS_n)
);

reset
#(
	.IN_RST_ACTIVE	("LOW"),
	.OUT_RST_ACTIVE	("LOW"),
	.CYCLE			(3)
)
inst_pixel_clk_rst
(
	.i_arst	(reset_n),
	.i_clk	(pixel_clk),
	.o_srst	(reset_pixel_n)
);
//============================================================================================= 
//
//=============================================================================================
///////////////////// Start of VGA gen ////////////////
//-----------------------------------------------------------//
// 1280*16 VGA
//-----------------------------------------------------------//
wire vs;					
wire de;	
wire hs;			
wire [7:0] rgb_r;
wire [7:0] rgb_g;
wire [7:0] rgb_b;

wire [7:0] y_444		;
wire [7:0] cb_444		;
wire [7:0] cr_444		;
wire 		 hs_444	;
wire 		 vs_444	;
wire 		 de_444		;

wire [7:0] y_422		;
wire [7:0] c_422		;
wire 		 vs_422	;
wire 		 hs_422	;
wire 		 de_422		;

color_bar_rgb #(
	.HS_POLORY 		(1'b0			),//   parameter HSA		 = 5,  //minimum value is pixel cnt value, eg: RGB888 - 2
	.VS_POLORY 		(1'b0			),//    parameter HBP		 = 5,   //minimum value is pixel cnt value, eg: RGB888 - 2
	.H_FRONT_PORCH 	(HFP/4			),//    parameter HFP		 = 1024,
	.H_SYNC 		(HSA/4			),//    parameter HACT_CNT	 = 1920,
	.H_VALID 		(HACT_CNT/4		),//    parameter VSA		 = 1,
	.H_BACK_PORCH 	(HBP/4			),//    parameter VBP		 = 1,
	.V_FRONT_PORCH 	(VFP			),//    parameter VFP		 = 100,
	.V_SYNC 		(VSA			),//    parameter VACT_CNT	 = 1080,
	.V_VALID 		(VACT_CNT		),//
	.V_BACK_PORCH 	(VBP			),//
	.TEST_MODE 		(2'd2)
	)u_color_bar_rgb(
	/*i*/.clk		(pixel_clk		),
	/*i*/.rst_n		(reset_pixel_n	),
	/*o*/.hs		(hs				),
	/*o*/.vs		(vs				),
	/*o*/.de		(de				),
	/*o*/.rgb_r		(rgb_r			),    //像素数据、红色分量
	/*o*/.rgb_g		(rgb_g			),    //像素数据、绿色分量
	/*o*/.rgb_b 	(rgb_b			)    //像素数据、蓝色分量
	
	);

rgb_to_ycbcr u_rgb_to_ycbcr(
	/*i*/.clk		(pixel_clk		),
	/*i*/.i_r_8b	(rgb_r			),
	/*i*/.i_g_8b	(rgb_g			),
	/*i*/.i_b_8b	(rgb_b			),
	
	/*i*/.i_h_sync	(hs				),
	/*i*/.i_v_sync	(vs				),
	/*i*/.i_data_en	(de	 			),
	
	/*o*/.o_y_8b	(y_444			),
	/*o*/.o_cb_8b	(cb_444			),
	/*o*/.o_cr_8b	(cr_444			),
	/*o*/.o_h_sync	(hs_444			),
	/*o*/.o_v_sync	(vs_444			),                                                                                                  
	/*o*/.o_data_en (de_444			)                                                                                       
	);

 yuv444_yuv422 u_yuv44_2yuv422(
	/*i*/.sys_clk	(pixel_clk		),
	
	/*i*/.line_end	(				),
    /*i*/.i_hs		(hs_444			),
	/*i*/.i_vs		(vs_444			),
	/*i*/.i_de		(de_444			),
	/*i*/.i_y		(y_444			),
	/*i*/.i_cb		(cb_444			),
	/*i*/.i_cr		(cr_444			),
	/*o*/.o_hs		(tx_out_hs		),
	/*o*/.o_vs		(tx_out_vs		),
	/*o*/.o_de		(tx_out_valid	),
	/*o*/.o_y		(y_422			),
	/*o*/.o_c		(c_422			)	
);
assign  tx_out_data = {y_422,c_422,y_422,c_422,y_422,c_422,y_422,c_422};

///////////////////// end of VGA gen ////////////////

reg		[5:0]	r_tx_axi_araddr_1P;
reg				r_tx_axi_arvalid_1P;
wire			w_tx_axi_arready;
wire	[31:0]	w_tx_axi_rdata;
wire			w_tx_axi_rvalid;
reg				r_tx_axi_rready_1P;

efx_csi2_tx inst_efx_csi2_tx
(
    .reset_n			(reset_n),
    .clk				(mipi_clk),
    .reset_byte_HS_n	(mipi_dphy_tx_reset_byte_HS_n),
    .clk_byte_HS		(mipi_dphy_tx_SLOWCLK),
    
    // LVDS clock lane   
	.Tx_LP_CLK_P		(mipi_dphy_tx_clk_LP_P_OUT),
    .Tx_LP_CLK_P_OE     (mipi_dphy_tx_clk_LP_P_OE),
	.Tx_LP_CLK_N		(mipi_dphy_tx_clk_LP_N_OUT),
    .Tx_LP_CLK_N_OE     (mipi_dphy_tx_clk_LP_N_OE),
    .Tx_HS_C            (mipi_dphy_tx_clk_HS_OUT),
	.Tx_HS_enable_C		(mipi_dphy_tx_HS_enable_C),
	
	// ----- DLane 0 -----------
    // LVDS data lane
    .Tx_LP_D_P			({mipi_dphy_tx_data3_LP_P_OUT, mipi_dphy_tx_data2_LP_P_OUT, mipi_dphy_tx_data1_LP_P_OUT, mipi_dphy_tx_data0_LP_P_OUT}),
    .Tx_LP_D_P_OE       ({mipi_dphy_tx_data3_LP_P_OE, mipi_dphy_tx_data2_LP_P_OE, mipi_dphy_tx_data1_LP_P_OE, mipi_dphy_tx_data0_LP_P_OE}),
    .Tx_LP_D_N			({mipi_dphy_tx_data3_LP_N_OUT, mipi_dphy_tx_data2_LP_N_OUT, mipi_dphy_tx_data1_LP_N_OUT, mipi_dphy_tx_data0_LP_N_OUT}),
    .Tx_LP_D_N_OE       ({mipi_dphy_tx_data3_LP_N_OE, mipi_dphy_tx_data2_LP_N_OE, mipi_dphy_tx_data1_LP_N_OE, mipi_dphy_tx_data0_LP_N_OE}),
    .Tx_HS_D_0			(mipi_dphy_tx_data0_HS_OUT),
	.Tx_HS_D_1			(mipi_dphy_tx_data1_HS_OUT),
	.Tx_HS_D_2			(mipi_dphy_tx_data2_HS_OUT),
	.Tx_HS_D_3			(mipi_dphy_tx_data3_HS_OUT),
	.Tx_HS_enable_D		({mipi_dphy_tx_data3_HS_OE, mipi_dphy_tx_data2_HS_OE, mipi_dphy_tx_data1_HS_OE, mipi_dphy_tx_data0_HS_OE}),

    //AXI4-Lite Interface
    .axi_clk		(mipi_clk), 
    .axi_reset_n	(reset_n),
    .axi_awaddr		(6'b0),//Write Address. byte address.
    .axi_awvalid	(1'b1),//Write address valid.
    .axi_awready	(),//Write address ready.
    .axi_wdata		(32'b0),//Write data bus.
    .axi_wvalid		(1'b0),//Write valid.
    .axi_wready		(),//Write ready.
    .axi_bvalid		(),//Write response valid.
    .axi_bready		(1'b0),//Response ready.      
    .axi_araddr		(r_tx_axi_araddr_1P),//Read address. byte address.
    .axi_arvalid	(r_tx_axi_arvalid_1P),//Read address valid.
    .axi_arready	(w_tx_axi_arready),//Read address ready.
    .axi_rdata		(w_tx_axi_rdata),//Read data.
    .axi_rvalid		(w_tx_axi_rvalid),//Read valid.
//    .axi_rready		(r_tx_axi_rready_1P),//Read ready.
    .axi_rready		(1'b1),//Read ready.
	
	.reset_pixel_n		(reset_pixel_n),
    .clk_pixel			(pixel_clk),
    .hsync_vc0			(tx_out_hs),
    .hsync_vc1			(1'b0),
    .hsync_vc2			(1'b0),
    .hsync_vc3			(1'b0),
    .vsync_vc0			(tx_out_vs),
    .vsync_vc1			(1'b0),
    .vsync_vc2			(1'b0),
    .vsync_vc3			(1'b0),
    .datatype			(DATATYPE),   // data type of the Long Packet
    .pixel_data			(tx_out_data),
    .pixel_data_valid	(tx_out_valid),
	.haddr              (HACT_CNT),  //for RAW8 word_count = HACT_CNT
	.line_num			(0),
	.frame_num			(0),	
    .irq				()
);

////////////////////////MIPI RX//////////////////////
logic rx_out_valid, rx_out_hs, rx_out_vs;
logic [PACK_BIT-1:0] rx_out_data;
logic [FIFO_WIDTH-1:0] rx_unpack_x;
logic [FIFO_WIDTH-1:0] rx_unpack_y;
logic rx_unpack_valid, rx_unpack_de, rx_unpack_hs, rx_unpack_vs;
logic [PIXEL_BIT-1:0] rx_unpack_data, rx_unpack_data_1P;
logic [FIFO_WIDTH-1:0] golden_x;
logic [FIFO_WIDTH-1:0] golden_y;
logic golden_valid, golden_de, golden_hs, golden_vs;
logic [PIXEL_BIT-1:0] golden_data;
logic r_pass, r_fail;
logic [11:0] flash_cnt;
logic [2:0] error_bit;

reg		[5:0]	r_rx_axi_araddr_1P;
reg				r_rx_axi_arvalid_1P;
wire			w_rx_axi_arready;
wire	[31:0]	w_rx_axi_rdata;
wire			w_rx_axi_rvalid;
reg				r_rx_axi_rready_1P;

mipi_csi_rx inst_efx_csi2_rx
(
    .reset_n			(reset_n),
    .clk				(mipi_clk),
    .reset_byte_HS_n	(mipi_dphy_rx_reset_byte_HS_n),
    .clk_byte_HS		(mipi_dphy_rx_clk_CLKOUT),
    .reset_pixel_n		(reset_pixel_n),
    .clk_pixel			(pixel_clk),  
    // LVDS clock lane   
	.Rx_LP_CLK_P		(mipi_dphy_rx_clk_LP_P_IN),
	.Rx_LP_CLK_N		(mipi_dphy_rx_clk_LP_N_IN),
	.Rx_HS_enable_C		(mipi_dphy_rx_clk_HS_ENA),
	.LVDS_termen_C		(mipi_dphy_rx_clk_HS_TERM),
	
	// ----- DLane 0 -----------
    // LVDS data lane
    .Rx_LP_D_P			({mipi_dphy_rx_data3_LP_P_IN, mipi_dphy_rx_data2_LP_P_IN, mipi_dphy_rx_data1_LP_P_IN, mipi_dphy_rx_data0_LP_P_IN}),
	.Rx_LP_D_N			({mipi_dphy_rx_data3_LP_N_IN, mipi_dphy_rx_data2_LP_N_IN, mipi_dphy_rx_data1_LP_N_IN, mipi_dphy_rx_data0_LP_N_IN}),
	.Rx_HS_D_0			(mipi_dphy_rx_data0_HS_IN),
	.Rx_HS_D_1			(mipi_dphy_rx_data1_HS_IN),	
	.Rx_HS_D_2			(mipi_dphy_rx_data2_HS_IN),
	.Rx_HS_D_3			(mipi_dphy_rx_data3_HS_IN),
	.Rx_HS_enable_D		({mipi_dphy_rx_data3_HS_ENA, mipi_dphy_rx_data2_HS_ENA, mipi_dphy_rx_data1_HS_ENA, mipi_dphy_rx_data0_HS_ENA}),
	.LVDS_termen_D		({mipi_dphy_rx_data3_HS_TERM, mipi_dphy_rx_data2_HS_TERM, mipi_dphy_rx_data1_HS_TERM, mipi_dphy_rx_data0_HS_TERM}),
	.fifo_rd_enable     ({mipi_dphy_rx_data3_FIFO_RD, mipi_dphy_rx_data2_FIFO_RD, mipi_dphy_rx_data1_FIFO_RD, mipi_dphy_rx_data0_FIFO_RD}),
	.fifo_rd_empty      ({mipi_dphy_rx_data3_FIFO_EMPTY, mipi_dphy_rx_data2_FIFO_EMPTY, mipi_dphy_rx_data1_FIFO_EMPTY, mipi_dphy_rx_data0_FIFO_EMPTY}),
	
	.DLY_enable_D       (),
	.DLY_inc_D          (),
	.u_dly_enable_D     (),
	.u_dly_inc_D        (),
	
    //AXI4-Lite Interface
    .axi_clk		(mipi_clk), 
    .axi_reset_n	(reset_n),
    .axi_awaddr		(6'b0),//Write Address. byte address.
    .axi_awvalid	(1'b0),//Write address valid.
    .axi_awready	(),//Write address ready.
    .axi_wdata		(32'b0),//Write data bus.
    .axi_wvalid		(1'b0),//Write valid.
    .axi_wready		(),//Write ready.           
    .axi_bvalid		(),//Write response valid.
    .axi_bready		(1'b0),//Response ready.      
    .axi_araddr		(r_rx_axi_araddr_1P),//Read address. byte address.
    .axi_arvalid	(r_rx_axi_arvalid_1P),//Read address valid.
    .axi_arready	(w_rx_axi_arready),//Read address ready.
    .axi_rdata		(w_rx_axi_rdata),//Read data.
    .axi_rvalid		(w_rx_axi_rvalid),//Read valid.
//    .axi_rready		(r_rx_axi_rready_1P),//Read ready.
    .axi_rready		(1'b1),//Read ready.
	
    .hsync_vc0			(rx_out_hs),
    .hsync_vc1			(),
    .hsync_vc2			(),
    .hsync_vc3			(),
    .vsync_vc0			(rx_out_vs),
    .vsync_vc1			(),
    .vsync_vc2			(),
    .vsync_vc3			(),
    .vc					(),
	.word_count			(word_count),
	.shortpkt_data_field(),
	.datatype			(datatype),        // RAW8
    .pixel_per_clk		(),
	.pixel_data			(rx_out_data),
    .pixel_data_valid	(rx_out_valid),
    .irq				()

);
reg rx_out_hs_r ;
reg [11:0] h_cnt = 'd0;
reg [11:0] h_cnt_o = 'd0;
always @( posedge pixel_clk )
begin
	rx_out_hs_r <= rx_out_hs;
end
wire pos_hs = {rx_out_hs_r,rx_out_hs} == 2'b01;

always @( posedge pixel_clk )
begin
	if(pos_hs )
		h_cnt <= 'd0;
	else 
		h_cnt <= rx_out_valid ? h_cnt + 1'b1 : h_cnt;
end
always @(posedge pixel_clk )
begin
	if( pos_hs )
	h_cnt_o <= h_cnt;
end
//------------- Unpack of RX pixel ---------------
//RAW8 for PIXEL_BIT 8, PACK_BIT 64
data_unpack
#(
	.PIXEL_BIT	(PIXEL_BIT),           
	.PACK_BIT	(PACK_BIT),  	          
	.FIFO_WIDTH	(FIFO_WIDTH)
)
inst_data_unpack
(
	.in_pclk	(pixel_clk),
	.in_rstn	(reset_pixel_n),
	
	.in_x		(r_x_active_1P),
	.in_y		(r_y_active_1P),
	.in_valid	(rx_out_valid),
	.in_de		(rx_out_hs),
	.in_hs		(rx_out_hs),
	.in_vs		(rx_out_vs),
	.in_data	(rx_out_data),
	
	.out_x		(rx_unpack_x),
	.out_y		(rx_unpack_y),
	.out_valid	(rx_unpack_valid),
	.out_de		(rx_unpack_de),
	.out_hs		(rx_unpack_hs),
	.out_vs		(rx_unpack_vs),
	.out_data	(rx_unpack_data)
);
//---------- End of unpack RX pixel -------------

//*******************************   
// MIPI-Rx-data comparator 
//*******************************   
pattern_gen
#(
    .PIXEL_BIT    (PIXEL_BIT),           
    .FIFO_WIDTH   (FIFO_WIDTH),                
    .H_ActivePix  (HACT_CNT),
    .V_ActivePix  (VACT_CNT)
)
inst_rx_pattern_gen
(
    .in_pclk    (pixel_clk),
    .in_rstn    (reset_pixel_n),
    
    .in_x        (rx_unpack_x),
    .in_y        (rx_unpack_y),
    .in_valid    (rx_unpack_valid),
    .in_de       (rx_unpack_de),
    .in_hs       (rx_unpack_hs),
    .in_vs       (rx_unpack_vs),
    .in_pattern  (1),
    
    .out_x        (golden_x),
    .out_y        (golden_y),
    .out_valid    (golden_valid),
    .out_de       (golden_de),
    .out_hs       (golden_hs),
    .out_vs       (golden_vs),
    .out_data     (golden_data)
);

always @(posedge pixel_clk or negedge reset_pixel_n) 
begin
    if (~reset_pixel_n) begin
        rx_out_valid_1P <= 1'b0;
        rx_out_hs_1P    <= 1'b0;
    end
	else begin
        rx_out_valid_1P <= rx_out_valid;
        rx_out_hs_1P    <= rx_out_hs;
    end
end

always @ (posedge pixel_clk or negedge reset_pixel_n)
begin
    if(~reset_pixel_n) begin
        rx_unpack_data_1P   <= {PIXEL_BIT{1'b0}};
        r_x_active_1P       <= {FIFO_WIDTH{1'b0}};
        r_y_active_1P       <= {FIFO_WIDTH{1'b0}};
        error_bit           <= 3'b000;
        r_fail              <= 1'b0;
        r_pass              <= 1'b0;
    end    
    else begin        
        rx_unpack_data_1P    <= rx_unpack_data;
        
        if (rx_out_valid_1P) begin
            r_x_active_1P    <= r_x_active_1P + 1'b1;
        end
        else if (~rx_out_hs) begin
            r_x_active_1P    <= {FIFO_WIDTH{1'b0}};
        end
       
        if (~rx_out_hs && rx_out_hs_1P) begin
            r_y_active_1P    <= r_y_active_1P + 1'b1;
        end
        else if (~rx_out_vs) begin
            r_y_active_1P    <= {FIFO_WIDTH{1'b0}};
        end
        
        if (golden_valid && error_bit == 3'b000) begin
            if (golden_data !== rx_unpack_data_1P) begin
                error_bit    <= error_bit + 1'b1;
                r_pass <= 1'b0;
            end
            else begin
                r_pass <= 1'b1;
            end
        end
        
        if (error_bit > 3'b000) r_fail <= 1'b1;
    end
end

always @(posedge pixel_clk or negedge reset_pixel_n) 
begin
    if (~reset_pixel_n) begin
        flash_cnt <= 12'b0;
    end
	else if (~r_fail && rx_out_hs && ~rx_out_hs_1P) begin
        flash_cnt <= flash_cnt + 1'b1;
    end
end

assign O_LED[0] = count_led[26];
assign O_LED[1] = r_fail && count_led[26];
assign O_LED[2] = r_pass && count_led[26];
assign O_LED[3] = flash_cnt[11];

////////////////////////////////

localparam	s_idle			= 2'b00;
localparam	s_wait_arready	= 2'b01;
localparam	s_wait_rvalid	= 2'b10;

reg		[1:0]	r_tx_dbg_fsm_1P;
reg		[8:0]	r_tx_dbg_reg_1P	[0:7];
reg		[1:0]	r_rx_dbg_fsm_1P;
reg		[14:0]	r_rx_dbg_reg_1P	[0:15];

always@(negedge reset_n or posedge mipi_clk)
begin
	if (~reset_n)
	begin
		r_tx_dbg_fsm_1P		<= s_idle;
		r_tx_axi_arvalid_1P	<= 1'b0;
		r_tx_axi_araddr_1P	<= 6'b0;
		r_tx_axi_rready_1P	<= 1'b0;
		
		r_rx_dbg_fsm_1P		<= s_idle;
		r_rx_axi_arvalid_1P	<= 1'b0;
		r_rx_axi_araddr_1P	<= 6'b0;
		r_rx_axi_rready_1P	<= 1'b0;
	end
	else
	begin
		r_tx_axi_rready_1P	<= 1'b0;
		r_rx_axi_rready_1P	<= 1'b0;
		
		case (r_tx_dbg_fsm_1P)
			s_idle:
			begin
				r_tx_dbg_fsm_1P		<= s_wait_arready;
				r_tx_axi_arvalid_1P	<= 1'b1;
			end
			
			s_wait_arready:
			begin
				if (w_tx_axi_arready)
				begin
					r_tx_dbg_fsm_1P		<= s_wait_rvalid;
					r_tx_axi_arvalid_1P	<= 1'b0;
				end
			end
			
			s_wait_rvalid:
			begin
				if (w_tx_axi_rvalid)
				begin
					r_tx_dbg_fsm_1P		<= s_wait_arready;
					r_tx_axi_arvalid_1P	<= 1'b1;
					r_tx_axi_rready_1P	<= 1'b1;
					r_tx_axi_araddr_1P	<= r_tx_axi_araddr_1P+6'h4;
					if (r_tx_axi_araddr_1P == 6'h18)
						r_tx_axi_araddr_1P	<= 6'b0;
					
					r_tx_dbg_reg_1P[r_tx_axi_araddr_1P[4:2]]	<= w_tx_axi_rdata[8:0];
				end
			end
		endcase
		
		case (r_rx_dbg_fsm_1P)
			s_idle:
			begin
				r_rx_dbg_fsm_1P		<= s_wait_arready;
				r_rx_axi_arvalid_1P	<= 1'b1;
			end
			
			s_wait_arready:
			begin
				if (w_rx_axi_arready)
				begin
					r_rx_dbg_fsm_1P		<= s_wait_rvalid;
					r_rx_axi_arvalid_1P	<= 1'b0;
				end
			end
			
			s_wait_rvalid:
			begin
				if (w_rx_axi_rvalid)
				begin
					r_rx_dbg_fsm_1P		<= s_wait_arready;
					r_rx_axi_arvalid_1P	<= 1'b1;
					r_rx_axi_rready_1P	<= 1'b1;
					r_rx_axi_araddr_1P	<= r_rx_axi_araddr_1P+6'h4;
					if (r_rx_axi_araddr_1P == 6'h28)
						r_rx_axi_araddr_1P	<= 6'b0;
					
					r_rx_dbg_reg_1P[r_rx_axi_araddr_1P[5:2]]	<= w_rx_axi_rdata[14:0];
/*					r_rx_axi_araddr_1P	<= r_rx_axi_araddr_1P+6'h10;
					if (r_rx_axi_araddr_1P == 6'h30)
						r_rx_axi_araddr_1P	<= 6'b0;
					
					r_rx_dbg_reg_1P[r_rx_axi_araddr_1P[5:4]]	<= w_rx_axi_rdata[14:0];*/
				end
			end
		endcase
	end
end

endmodule
