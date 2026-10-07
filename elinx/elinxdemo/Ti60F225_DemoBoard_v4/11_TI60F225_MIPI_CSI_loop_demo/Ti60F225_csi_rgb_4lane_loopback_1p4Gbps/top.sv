
// synopsys translate_off
`timescale 1 ns / 1 ps													
// synopsys translate_on

module top #(   //csi2 example design
    parameter PIXEL_BIT  = 24,
    parameter PACK_BIT   = 48,
    parameter HSA		 = 44,  //minimum value is pixel cnt value, eg: RGB888 - 2
    parameter HBP		 = 148,   //minimum value is pixel cnt value, eg: RGB888 - 2
    parameter HFP		 = 88,
    parameter HACT_CNT	     = 1920,
    parameter VSA		 = 5,
    parameter VBP		 = 4,
    parameter VFP		 = 36,
    parameter VACT_CNT	     = 1080,
    parameter DATATYPE = 6'h24     //24 - RGB888
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
logic mipi_clk_reset_n;
logic mipi_dphy_rx_reset_byte_HS_n;
logic reset_pixel_n;
logic mipi_dphy_tx_reset_byte_HS_n;
logic [26:0] count_led;
logic [5:0] datatype;
logic [15:0] word_count;


logic tx_out_valid;
logic tx_out_hs;
logic tx_out_vs;
logic [PACK_BIT-1:0] tx_out_data;
reg [22:0] cnt = 'd0;
wire check_pass;
wire check_fail;
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
//================================================
//
//================================================
reg data_en= 'd0;
always @( posedge pixel_clk or negedge reset_pixel_n)
begin
    if( !reset_pixel_n )
        cnt <= 'd0;
    else 
        cnt <= cnt + 1'b1;
end
always @( posedge pixel_clk or negedge reset_pixel_n )
begin
    if( !reset_pixel_n )
        data_en <= 1'b0;
    else if( cnt[22] )
        data_en <= 1'b1;
end

color_bar_rgb # (
    .HS_POLORY(1'b0),
    .VS_POLORY(1'b0),
    .SYMBOL_WIDTH(8),
    .SYMBOL_NUM(3),
    .PAR_PIXEL_NUM(2),
    .HFP(HFP),
    .HST(HSA),
    .HACT(HACT_CNT),
    .HBP(HBP),
    .VFP(VFP),
    .VST(VSA),
    .VACT(VACT_CNT),
    .VBP(VBP),
    .TEST_MODE(2'd0)
  )
  color_bar_rgb_inst (
    .clk(pixel_clk),
    .rst_n(reset_pixel_n ),
    .i_cfg_vid(),
    .h_cnt(h_cnt),
    .v_cnt(v_cnt),
    .hs(tx_out_hs),
    .vs(tx_out_vs),
    .de(tx_out_valid),
    .o_vid_data(tx_out_data)
  );

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
    .reset_pixel_n		(reset_pixel_n),
    .clk_pixel			(pixel_clk),
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
logic rx_out_valid;
logic rx_out_hs;
logic rx_out_vs;
logic [PACK_BIT-1:0] rx_out_data;


logic [11:0] flash_cnt;

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


assign O_LED[0] = count_led[26];
assign O_LED[1] = count_led[26];
assign O_LED[2] = count_led[26];
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
				end
			end
		endcase
	end
end

color_bar_checker # (
    .DATA_WIDTH(PACK_BIT)
  )
  color_bar_checker_inst (
    .clk(pixel_clk),
    .rst_n(reset_pixel_n),
    .i_hs(rx_out_hs),
    .i_vs(rx_out_vs),
    .i_de(rx_out_valid),
    .vin(rx_out_data),
    .check_fail(check_fail),
    .check_pass(check_pass)
  );



endmodule
