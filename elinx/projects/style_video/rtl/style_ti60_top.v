
/////////////////////////////////////////////////////////////////////////////
//
// Copyright (C) 2013-2021 Efinix Inc. All rights reserved.
//
// Description:
// Example top file for ti60f225 dev kit OOB design
//
// Language:  Verilog 2001
//Ti60f225_sc431hai2hdmi_v6：
//使用了最新版本的framebuffer_v3;
// ------------------------------------------------------------------------------

/////////////////////////////////////////////////////////////////////////////////
//`define SOFT_TAP 1
`include "../efinity/vendor/rtl/ddr3_controller/ddr3_parameter.vh"
// `include "define.v"

module style_ti60_top #(

	parameter                       RANK_RATIO         = 1,       // # of unique CS outputs per rank
	parameter                       ASYN_AXI_CLK       = `ASYN_AXI_CLK, 
	parameter                       RANKS              = `RANKS,
	parameter                       CK_WIDTH           = `CK_WIDTH,       // # of CK/CK# outputs to memory   
	parameter                       CKE_WIDTH          = `CKE_WIDTH,       // # of cke outputs
	parameter                       CS_WIDTH           = `CS_WIDTH,       // # of unique CS outputs
	parameter                       BANK_WIDTH         = `BANK_WIDTH,       // # of bank bits
	parameter                       ROW_WIDTH          = `ROW_WIDTH,       // DRAM address bus width
	parameter                       COL_WIDTH          = `COL_WIDTH,      // column address width
	parameter                       DM_WIDTH           = `DM_WIDTH,       // # of DM (data mask)
	parameter                       DQS_WIDTH          = `DQS_WIDTH,       // # of DQS (strobe)
	parameter                       DQ_WIDTH           = `DQ_WIDTH,      // # of DQ (data)
	parameter                       ODT_WIDTH          = `ODT_WIDTH,
	parameter                       DQ_CNT_WIDTH       = `DQ_CNT_WIDTH,       // = ceil(log2(DQ_WIDTH))
	parameter                       DQS_CNT_WIDTH      = `DQS_CNT_WIDTH,       // = ceil(log2(DQS_WIDTH))  
	parameter                       DRAM_WIDTH         = `DRAM_WIDTH,       // # of DQ per DQS   
	parameter                       DATA_WIDTH         = `DATA_WIDTH,
	parameter                       ADDR_WIDTH         = `ADDR_WIDTH,    
	parameter                       AXI_ID_WIDTH       = `AXI_ID_WIDTH,
	parameter                       AXI_ADDR_WIDTH     = `AXI_ADDR_WIDTH,
	parameter                       AXI_DATA_WIDTH     = `AXI_DATA_WIDTH
)
(


   //Clocks 
	input	wire	i_arstn,
    input wire key1_n, key2_n, key3_n,
    input	wire	i_mipi_rx_pclk,
    input wire  vid_clk_dvi2,
    input wire hdmi_tx_slow_clk,
    input wire CLK_5M,
    input  wire CLK_25M,
	output  wire    pll_inst1_RSTN,
	input	wire	i_pll_locked,
	input 	wire  	pll_locked,
	output  wire    pll_inst4_RSTN,
	input   wire    pll_inst4_LOCKED,
	output  wire  	USER_PLL_RSTN,
    output 	wire 	DDR3_PLL_RSTN,
	input 	wire  	user_pll_locked,
    //CSI Interface
    input	 wire		io_cam_sda_IN,
    output wire   io_cam_sda_OUT,
    output wire		io_cam_sda_OE,

    output io_cam_scl_OUT,
    input io_cam_scl_IN,
    output io_cam_scl_OE,

    output	wire		o_cam_rst_p,
    
    input	wire		i_cam_ck_LP_P_IN,
    input	wire		i_cam_ck_LP_N_IN,
    output	wire		o_cam_ck_HS_TERM,
    output	wire		o_cam_ck_HS_ENA,
    input	wire		i_cam_ck_CLKOUT,
    
    input	wire	[7:0]			cam_d0_HS_IN,
    input	  wire		      cam_d0_LP_P_IN,
    input	  wire		      cam_d0_LP_N_IN,
    output	wire		      cam_d0_HS_TERM,
    output	wire		      cam_d0_HS_ENA,
    output	wire		      cam_d0_RST,
    output	wire		      cam_d0_FIFO_RD,
    input	  wire		      cam_d0_FIFO_EMPTY,
    
    input 	wire	[7:0]			cam_d1_HS_IN,
    input	  wire		        cam_d1_LP_P_IN,
    input	  wire		        cam_d1_LP_N_IN,
    output	wire		        cam_d1_HS_TERM,
    output	wire		        cam_d1_HS_ENA,
    output	wire		        cam_d1_RST,
    output	wire		        cam_d1_FIFO_RD,
    input	  wire		        cam_d1_FIFO_EMPTY,
    
    input 	wire	[7:0]			cam_d2_HS_IN,
    input	  wire		        cam_d2_LP_P_IN,
    input	  wire		        cam_d2_LP_N_IN,
    output	wire		        cam_d2_HS_TERM,
    output	wire		        cam_d2_HS_ENA,
    output	wire		        cam_d2_RST,
    output	wire		        cam_d2_FIFO_RD,
    input	  wire		        cam_d2_FIFO_EMPTY,  
   
    input 	wire	[7:0]			cam_d3_HS_IN,
    input	  wire		        cam_d3_LP_P_IN,
    input	  wire		        cam_d3_LP_N_IN,
    output	wire		        cam_d3_HS_TERM,
    output	wire		        cam_d3_HS_ENA,
    output	wire		        cam_d3_RST,
    output	wire		        cam_d3_FIFO_RD,
    input	  wire		        cam_d3_FIFO_EMPTY,

	
	input 					tx_cal_clk_90edge,
  	input 					rx_cal_clk,
  	input 					tx_cal_clk,
	input                              core_clk,     // CORE CLK @ 100MHz
	input                              sdram_clk,    // SDRAM CK @ 400MHz
	// PLL status flags  
	output [2:0]                       pll_shift,  
	output [4:0]                       pll_shift_sel,
	output                             pll_shift_ena,  
	// memory interface ports
	output                             ddr_ck_hi,
	output                             ddr_ck_lo,
	output                             ddr_reset_n,
	output [CKE_WIDTH-1:0]             ddr_cke,     
	output [ROW_WIDTH-1:0]             ddr_addr,
	output [BANK_WIDTH-1:0]            ddr_ba,
	output                             ddr_cas_n,
 
	output [CS_WIDTH*RANK_RATIO-1:0]   ddr_cs_n,
	output                             ddr_ras_n,
	output                             ddr_we_n,
	
	input  [DQS_WIDTH-1:0]             ddr_dqs_in_hi,
	input  [DQS_WIDTH-1:0]             ddr_dqs_in_lo,
	input  [DQ_WIDTH-1:0]              ddr_dq_in_hi,
	input  [DQ_WIDTH-1:0]              ddr_dq_in_lo,
	
	output [DQS_WIDTH-1:0]             ddr_dqs_oe,
	output [DQS_WIDTH-1:0]             ddr_dqs_oe_n,
	output [DQ_WIDTH-1:0]              ddr_dq_oe,  
	output [DQS_WIDTH-1:0]             ddr_dqs_out_hi,
	output [DQS_WIDTH-1:0]             ddr_dqs_out_lo,
	output [DQ_WIDTH-1:0]              ddr_dq_out_hi,
	output [DQ_WIDTH-1:0]              ddr_dq_out_lo,
	output [DM_WIDTH-1:0]              ddr_dm_hi,
	output [DM_WIDTH-1:0]              ddr_dm_lo,
	output [ODT_WIDTH-1:0]             ddr_odt,

       //LED
       output [3:0] led,

       // MIPI DSI
       input	wire	                     i_mipi_tx_pclk		,
       output	wire	                     mipi_dp_clk_LP_P_OUT		,
       output	wire	                     mipi_dp_clk_LP_N_OUT		,
       output	wire	[7:0] 	              mipi_dp_clk_HS_OUT		,
       output	wire	                     mipi_dp_clk_HS_OE		,
       output	wire	                     mipi_dp_data3_LP_P_OUT	,
       output	wire	                     mipi_dp_data2_LP_P_OUT	,
       output	wire	                     mipi_dp_data1_LP_P_OUT	,
       output	wire	                     mipi_dp_data0_LP_P_OUT	,
       output	wire	                     mipi_dp_data3_LP_N_OUT	,
       output	wire	                     mipi_dp_data2_LP_N_OUT	,
       output	wire	                     mipi_dp_data1_LP_N_OUT	,
       output	wire	                     mipi_dp_data0_LP_N_OUT	,
       output	wire	[7:0] 	              mipi_dp_data0_HS_OUT	       ,
       output	wire	[7:0] 	              mipi_dp_data1_HS_OUT	       ,
       output	wire	[7:0] 	              mipi_dp_data2_HS_OUT	       ,
       output	wire	[7:0] 	              mipi_dp_data3_HS_OUT	       ,
       output	wire	                     mipi_dp_data3_HS_OE		,
       output	wire	                     mipi_dp_data2_HS_OE		,
       output	wire	                     mipi_dp_data1_HS_OE		,
       output	wire	                     mipi_dp_data0_HS_OE		,

       output	wire	                     mipi_dp_clk_RST		,
       output	wire	                     mipi_dp_data0_RST		,
       output	wire	                     mipi_dp_data1_RST		,
       output	wire	                     mipi_dp_data2_RST		,
       output	wire	                     mipi_dp_data3_RST		,
       output	wire	                     mipi_dp_clk_LP_P_OE		,
       output	wire	                     mipi_dp_clk_LP_N_OE		,
       output	wire	                     mipi_dp_data3_LP_P_OE	,
       output	wire	                     mipi_dp_data3_LP_N_OE	,
       output	wire	                     mipi_dp_data2_LP_P_OE	,
       output	wire	                     mipi_dp_data2_LP_N_OE	,
       output	wire	                     mipi_dp_data1_LP_P_OE	,
       output	wire	                     mipi_dp_data1_LP_N_OE	,
       output	wire	                     mipi_dp_data0_LP_P_OE	,
       output	wire	                     mipi_dp_data0_LP_N_OE	,

       input  wire	                     mipi_dp_data0_LP_P_IN	,
       input  wire	                     mipi_dp_data0_LP_N_IN	,
       output	wire	                     LCD_RST_P			,
       output wire                        LCD_POWER			,

       // hdmi interface

    output tmds_tx_clk_TX_OE,
    output [9:0] tmds_tx_clk_TX_DATA,
    output tmds_tx_clk_TX_RST,
    output tmds_tx_data0_TX_OE,
    output [9:0] tmds_tx_data0_TX_DATA,
    output tmds_tx_data0_TX_RST,
    output tmds_tx_data1_TX_OE,
    output [9:0] tmds_tx_data1_TX_DATA,
    output tmds_tx_data1_TX_RST,
    output tmds_tx_data2_TX_OE,
    output [9:0] tmds_tx_data2_TX_DATA,
    output tmds_tx_data2_TX_RST


);


// Verified V4/J5 peripheral shell. Keep D-PHY/DDR electrical settings isolated
// from the portable platform core; no Xilinx primitive is used in this project.
wire w_arstn=i_arstn & i_pll_locked & pll_locked & user_pll_locked & pll_inst4_LOCKED;
wire core_rst_n,camera_rst_n,pixel_rst_n,mipi_core_reset_n,mipi_byte_reset_n;
wire w_mipi_rx_pclk_arstn;
style_reset_sync r_core(core_clk,w_arstn,core_rst_n);
style_reset_sync r_camera(i_mipi_rx_pclk,w_arstn,camera_rst_n);
style_reset_sync r_video(hdmi_tx_slow_clk,w_arstn,pixel_rst_n);
style_reset_sync r_mipi(core_clk,w_arstn,mipi_core_reset_n);
style_reset_sync r_byte(i_cam_ck_CLKOUT,w_arstn,mipi_byte_reset_n);
assign w_mipi_rx_pclk_arstn=camera_rst_n;
assign pll_inst1_RSTN=i_arstn;
assign USER_PLL_RSTN=i_arstn;
assign DDR3_PLL_RSTN=i_arstn;
assign pll_inst4_RSTN=i_arstn;
assign cam_d0_RST=~mipi_core_reset_n;assign cam_d1_RST=~mipi_core_reset_n;
assign cam_d2_RST=~mipi_core_reset_n;assign cam_d3_RST=~mipi_core_reset_n;
wire i_mipi_clk=core_clk;
wire w_mipi_rx_vs,w_mipi_rx_hs,w_mipi_rx_de;
wire [63:0] w_mipi_rx_data;
wire [15:0] mipi_debug_out;
csi_rx_controller inst_efx_csi2_rx
		(
              .reset_n			(mipi_core_reset_n),
              .clk				(i_mipi_clk),
              .reset_byte_HS_n	(mipi_byte_reset_n),
              .clk_byte_HS		  (i_cam_ck_CLKOUT),
              .reset_pixel_n		(w_mipi_rx_pclk_arstn),
              .clk_pixel			  (i_mipi_rx_pclk),
              
              .Rx_LP_CLK_P		  (i_cam_ck_LP_P_IN),
              .Rx_LP_CLK_N		  (i_cam_ck_LP_N_IN),
              .Rx_HS_enable_C		(o_cam_ck_HS_ENA),
              .LVDS_termen_C		(o_cam_ck_HS_TERM),
              
              .Rx_LP_D_P			({cam_d3_LP_P_IN, cam_d2_LP_P_IN, cam_d1_LP_P_IN, cam_d0_LP_P_IN}),//(r_mipi_rx_data_LP_P_IN_2P),
              .Rx_LP_D_N			({cam_d3_LP_N_IN, cam_d2_LP_N_IN, cam_d1_LP_N_IN, cam_d0_LP_N_IN}),//(r_mipi_rx_data_LP_N_IN_2P),
              .Rx_HS_D_0			(cam_d0_HS_IN),//(r_mipi_rx_data_HS_IN_2P[0*8+:8]),
              .Rx_HS_D_1			(cam_d1_HS_IN),//(r_mipi_rx_data_HS_IN_2P[1*8+:8]),
              .Rx_HS_D_2			(cam_d2_HS_IN),
              .Rx_HS_D_3			(cam_d3_HS_IN),
              .Rx_HS_D_4			(),
              .Rx_HS_D_5			(),
              .Rx_HS_D_6			(),
              .Rx_HS_D_7			(),
              .Rx_HS_enable_D		({cam_d3_HS_ENA    ,cam_d2_HS_ENA    ,cam_d1_HS_ENA    ,cam_d0_HS_ENA    }),//( w_cam_d_HS_ENA),
              .LVDS_termen_D		({cam_d3_HS_TERM   ,cam_d2_HS_TERM   ,cam_d1_HS_TERM   ,cam_d0_HS_TERM   }),
              .fifo_rd_enable		({cam_d3_FIFO_RD   ,cam_d2_FIFO_RD   ,cam_d1_FIFO_RD   ,cam_d0_FIFO_RD   }),
              .fifo_rd_empty		({cam_d3_FIFO_EMPTY,cam_d2_FIFO_EMPTY,cam_d1_FIFO_EMPTY,cam_d0_FIFO_EMPTY}),
              .DLY_enable_D		       (),
              .DLY_inc_D			(),
              .u_dly_enable_D		(),
              .u_dly_inc_D		       (),
              
              .axi_clk			(1'b0),
              .axi_reset_n		       (1'b0),
              .axi_awaddr			(6'b0),
              .axi_awvalid		       (1'b0),
              .axi_awready		       (),
              .axi_wdata			(32'b0),
              .axi_wvalid			(1'b0),
              .axi_wready			(),
              
              .axi_bvalid			(),
              .axi_bready			(1'b0),
              .axi_araddr			(6'b0),
              .axi_arvalid		       (1'b0),
              .axi_arready		       (),
              .axi_rdata			(),
              .axi_rvalid			(),
              .axi_rready			(1'b1),
              
              .hsync_vc0			(w_mipi_rx_hs),
              .hsync_vc1			(),
              .hsync_vc2			(),
              .hsync_vc3			(),
              .vsync_vc0			(w_mipi_rx_vs),
              .vsync_vc1			(),
              .vsync_vc2			(),
              .vsync_vc3			(),
              .vc				(),
              .word_count			(),
              .shortpkt_data_field        (),
              .datatype			(),
              .pixel_per_clk		(),
              .pixel_data			(w_mipi_rx_data),
              .pixel_data_valid	       (w_mipi_rx_de),
              .irq				(),
              .mipi_debug_out(mipi_debug_out)
		);
// Standalone initializer is retained only until the teammate's I2C driver is
// connected. Future integration must choose ONE I2C owner, never both at once.
wire scl_padoen_o,sda_padoen_o;
reg [12:0] i2c_rst_cnt;
wire i2c_reset_n;
style_reset_sync r_i2c(CLK_5M,w_arstn,i2c_reset_n);
always @(posedge CLK_5M or negedge i2c_reset_n)
    if(!i2c_reset_n)i2c_rst_cnt<=0;
    else if(!i2c_rst_cnt[12])i2c_rst_cnt<=i2c_rst_cnt+1'b1;
wire camera_config_done;
(* async_reg="true" *) reg [1:0] config_done_sync;
always @(posedge core_clk or negedge core_rst_n)
    if(!core_rst_n)config_done_sync<=0;else config_done_sync<={config_done_sync[0],camera_config_done};
style_camera_initializer camera_initializer(.clk(CLK_5M),.rst_n(i2c_rst_cnt[12]),.config_done(camera_config_done),
    .scl_pad_i(io_cam_scl_IN),.scl_pad_o(io_cam_scl_OUT),.scl_padoen_o(scl_padoen_o),
    .sda_pad_i(io_cam_sda_IN),.sda_pad_o(io_cam_sda_OUT),.sda_padoen_o(sda_padoen_o));
assign io_cam_scl_OE=~scl_padoen_o;assign io_cam_sda_OE=~sda_padoen_o;
assign o_cam_rst_p=~w_arstn;
// Decoded CSI -> reusable acquisition module -> platform camera port.
wire core_cam_valid,core_cam_ready,core_cam_sof,core_cam_eol,core_cam_eof;
wire [23:0] core_cam_rgb;
wire [31:0] core_cam_id,core_abort_id;
wire core_abort_valid,camera_abort_fault;
wire [10:0] cam_wr_level,cam_rd_level;
wire [31:0] camera_frames_core,camera_drops_core,camera_errors_core;
wire cfa_mean_valid;
wire [39:0] cfa_mean_data;
style_camera_capture #(
    .BAYER_PATTERN(3),
    .DYNAMIC_WB(1),
    .TONE_ENABLE(1),
    .GAMMA_TENTHS(18),
    .STATS_ENABLE(1),
    .BLACK_LEVEL_A(65),
    .BLACK_LEVEL_B(66),
    .BLACK_LEVEL_C(66),
    .BLACK_LEVEL_D(67),
    .WB_GAIN_R_Q8(493),
    .WB_GAIN_G_Q8(256),
    .WB_GAIN_B_Q8(504)
) camera_capture(
    .camera_clk(i_mipi_rx_pclk),.camera_rst_n(camera_rst_n),
    .core_clk(core_clk),.core_rst_n(core_rst_n),.async_rst_n(w_arstn),
    .s_vs(w_mipi_rx_vs),.s_hs(w_mipi_rx_hs),.s_valid(w_mipi_rx_de),.s_raw(w_mipi_rx_data[39:0]),
    .wb_r_q8(wb_request_r),.wb_g_q8(11'd256),.wb_b_q8(wb_request_b),
    .m_rgb(core_cam_rgb),.m_valid(core_cam_valid),.m_ready(core_cam_ready),
    .m_sof(core_cam_sof),.m_eol(core_cam_eol),.m_eof(core_cam_eof),.m_frame_id(core_cam_id),
    .m_abort(core_abort_valid),.m_abort_frame_id(core_abort_id),
    .input_frames(camera_frames_core),.drop_frames(camera_drops_core),.error_frames(camera_errors_core),
    .abort_queue_fault(camera_abort_fault),.camera_fifo_level(cam_wr_level),.core_fifo_level(cam_rd_level),
    .raw_mean_valid(cfa_mean_valid),.raw_mean_data(cfa_mean_data));
wire cal_done,app_sr_active,app_ref_ack,app_zq_ack;
wire [AXI_ID_WIDTH-1:0] s_axi_awid;
wire [AXI_ADDR_WIDTH-1:0] s_axi_awaddr;
wire [8-1:0] s_axi_awlen;
wire [3-1:0] s_axi_awsize;
wire [2-1:0] s_axi_awburst;
wire s_axi_awlock;
wire [4-1:0] s_axi_awcache;
wire [3-1:0] s_axi_awprot;
wire s_axi_awvalid;
wire s_axi_awready;
wire [AXI_DATA_WIDTH-1:0] s_axi_wdata;
wire [AXI_DATA_WIDTH/8-1:0] s_axi_wstrb;
wire s_axi_wlast;
wire s_axi_wvalid;
wire s_axi_wready;
wire [AXI_ID_WIDTH-1:0] s_axi_bid;
wire [2-1:0] s_axi_bresp;
wire s_axi_bvalid;
wire s_axi_bready;
wire [AXI_ID_WIDTH-1:0] s_axi_arid;
wire [AXI_ADDR_WIDTH-1:0] s_axi_araddr;
wire [8-1:0] s_axi_arlen;
wire [3-1:0] s_axi_arsize;
wire [2-1:0] s_axi_arburst;
wire s_axi_arlock;
wire [4-1:0] s_axi_arcache;
wire [3-1:0] s_axi_arprot;
wire s_axi_arvalid;
wire s_axi_arready;
wire [AXI_ID_WIDTH-1:0] s_axi_rid;
wire [AXI_DATA_WIDTH-1:0] s_axi_rdata;
wire [2-1:0] s_axi_rresp;
wire s_axi_rlast;
wire s_axi_rvalid;
wire s_axi_rready;
assign s_axi_awlock=0;assign s_axi_arlock=0;
assign s_axi_awcache=0;assign s_axi_arcache=0;assign s_axi_awprot=0;assign s_axi_arprot=0;
ddr3_top                 u_ddr3_top
(

.axi_clk                (core_clk            ),
.core_clk               (core_clk            ),
.sdram_clk              (sdram_clk           ),  
.rx_cal_clk             (rx_cal_clk          ),
.tx_cal_clk             (tx_cal_clk          ),
.tx_cal_clk_90edge      (tx_cal_clk_90edge   ),
.rstn                   (w_arstn             ),      
.pll_shift              (pll_shift           ),
.pll_shift_sel          (pll_shift_sel       ),
.pll_shift_ena          (pll_shift_ena       ),       
///////////////DDR BUS
.ddr_ck_hi              (ddr_ck_hi           ),
.ddr_ck_lo              (ddr_ck_lo           ),
.ddr_cke                (ddr_cke             ),    
.ddr_reset_n            (ddr_reset_n         ),
.ddr_cs_n               (ddr_cs_n            ),
.ddr_ras_n              (ddr_ras_n           ),
.ddr_cas_n              (ddr_cas_n           ),
.ddr_we_n               (ddr_we_n            ),     
.ddr_addr               (ddr_addr            ),
.ddr_ba                 (ddr_ba              ),

.ddr_dqs_oe             (ddr_dqs_oe          ),
.ddr_dqs_oe_n           (ddr_dqs_oe_n        ),
.ddr_dq_oe              (ddr_dq_oe           ),
.ddr_dqs_in_hi          (ddr_dqs_in_hi       ),
.ddr_dqs_in_lo          (ddr_dqs_in_lo       ),
.ddr_dq_in_hi           (ddr_dq_in_hi        ),
.ddr_dq_in_lo           (ddr_dq_in_lo        ),

.ddr_dqs_out_hi         (ddr_dqs_out_hi      ),
.ddr_dqs_out_lo         (ddr_dqs_out_lo      ),
.ddr_dq_out_hi          (ddr_dq_out_hi       ),
.ddr_dq_out_lo          (ddr_dq_out_lo       ),

.ddr_dm_hi              (ddr_dm_hi           ),
.ddr_dm_lo              (ddr_dm_lo           ),
.ddr_odt                (ddr_odt             ),

// Application interface ports
.app_sr_req                     (1'b0),
.app_ref_req                    (1'b0),
.app_zq_req                     (1'b0),
.app_sr_active                  (app_sr_active),
.app_ref_ack                    (app_ref_ack),
.app_zq_ack                     (app_zq_ack),

// Slave Interface Write Address Ports
.s_axi_awid                     (s_axi_awid        ),
.s_axi_awaddr                   (s_axi_awaddr      ),
.s_axi_awlen                    (s_axi_awlen       ),
.s_axi_awsize                   (s_axi_awsize      ),
.s_axi_awburst                  (s_axi_awburst     ),
.s_axi_awlock                   (s_axi_awlock      ),
.s_axi_awcache                  (s_axi_awcache     ),
.s_axi_awprot                   (s_axi_awprot      ),
.s_axi_awqos                    (4'h0              ),
.s_axi_awvalid                  (s_axi_awvalid     ),
.s_axi_awready                  (s_axi_awready     ),
// Slave Interface Write Data Ports
.s_axi_wdata                    (s_axi_wdata       ),
.s_axi_wstrb                    (s_axi_wstrb       ),
.s_axi_wlast                    (s_axi_wlast       ),
.s_axi_wvalid                   (s_axi_wvalid      ),
.s_axi_wready                   (s_axi_wready      ),
// Slave Interface Write Response Ports
.s_axi_bid                      (s_axi_bid         ),
.s_axi_bresp                    (s_axi_bresp       ),
.s_axi_bvalid                   (s_axi_bvalid      ),
.s_axi_bready                   (s_axi_bready      ),
// Slave Interface Read Address Ports
.s_axi_arid                     (s_axi_arid        ),
.s_axi_araddr                   (s_axi_araddr      ),
.s_axi_arlen                    (s_axi_arlen       ),
.s_axi_arsize                   (s_axi_arsize      ),
.s_axi_arburst                  (s_axi_arburst     ),
.s_axi_arlock                   (s_axi_arlock      ),
.s_axi_arcache                  (s_axi_arcache     ),
.s_axi_arprot                   (s_axi_arprot      ),
.s_axi_arqos                    (4'h0              ),
.s_axi_arvalid                  (s_axi_arvalid     ),
.s_axi_arready                  (s_axi_arready     ),
// Slave Interface Read Data Ports
.s_axi_rid                      (s_axi_rid         ),
.s_axi_rdata                    (s_axi_rdata       ),
.s_axi_rresp                    (s_axi_rresp       ),
.s_axi_rlast                    (s_axi_rlast       ),
.s_axi_rvalid                   (s_axi_rvalid      ),
.s_axi_rready                   (s_axi_rready      ),
//DEBUG       
.wrlvl_dq_check                 (wrlvl_dq_check    ) ,
.rd_level_dqs_check             (rd_level_dqs_check) ,
.init_cur_state                 (init_cur_state    ) ,
.idelay_ld                      (idelay_ld         ) ,
.mpr_rdlvl_dly                  (mpr_rdlvl_dly     ) ,
.cal_done                       (cal_done          ) 
);
wire [23:0] display_rgb,video_rgb;
wire display_valid,display_ready,display_ack,display_flush,front_valid,refresh_request,safe_window;
wire [31:0] front_id,underflows,underflows_core,captured_count,processed_count,displayed_count,drop_count,error_count;
wire [15:0] capture_fps,process_fps,video_x,video_y;
wire [1:0] mode;
wire bypass_active,fatal_fault,irq;
wire video_de,video_hs,video_vs;
style_ddr_framebuffer #(.ID_WIDTH(AXI_ID_WIDTH),.FORCE_BYPASS(1),.PERF_ENABLE(1)) framebuffer(
    .clk(core_clk),.rst_n(core_rst_n),.cal_ready(cal_done && config_done_sync[1] && !camera_abort_fault),
    .cam_rgb(core_cam_rgb),.cam_valid(core_cam_valid),.cam_ready(core_cam_ready),
    .cam_sof(core_cam_sof),.cam_eol(core_cam_eol),.cam_eof(core_cam_eof),.cam_frame_id(core_cam_id),
    .cam_abort(core_abort_valid),.cam_abort_id(core_abort_id),
    .camera_frames(camera_frames_core),.camera_drops(camera_drops_core),.camera_errors(camera_errors_core),
    .display_refresh_request(refresh_request),.display_safe_window(safe_window),
    .display_refresh_ack(display_ack),.display_flush(display_flush),
    .display_rgb(display_rgb),.display_valid(display_valid),.display_ready(display_ready),
    .front_valid(front_valid),.front_frame_id(front_id),.display_mode(mode),
    .capture_fps(capture_fps),.process_fps(process_fps),.underflow_count(underflows_core),.bypass_active(bypass_active),
    .paddr(12'b0),.psel(1'b0),.penable(1'b0),.pwrite(1'b0),.pwdata(32'b0),.prdata(),.pready(),.pslverr(),.irq(irq),
    .accel_input_rgb(),.accel_input_valid(),.accel_input_ready(1'b0),
    .accel_input_sof(),.accel_input_eol(),.accel_input_eof(),.accel_input_frame_id(),
    .accel_output_rgb(24'b0),.accel_output_valid(1'b0),.accel_output_ready(),
    .accel_output_sof(1'b0),.accel_output_eol(1'b0),.accel_output_eof(1'b0),.accel_output_frame_id(32'b0),.accel_start(),.accel_abort(),
    .captured_count(captured_count),.processed_count(processed_count),.displayed_count(displayed_count),
    .drop_count(drop_count),.error_count(error_count),.fatal_fault(fatal_fault),
    .perf_camera_level({5'd0,cam_rd_level}),.perf_display_level({3'd0,display_fifo_level}),
    .perf_snapshot(perf_snapshot),.perf_snapshot_valid(perf_snapshot_valid),
    .m_axi_awid(s_axi_awid),
    .m_axi_awaddr(s_axi_awaddr),
    .m_axi_awlen(s_axi_awlen),
    .m_axi_awsize(s_axi_awsize),
    .m_axi_awburst(s_axi_awburst),
    .m_axi_awvalid(s_axi_awvalid),
    .m_axi_awready(s_axi_awready),
    .m_axi_wdata(s_axi_wdata),
    .m_axi_wstrb(s_axi_wstrb),
    .m_axi_wlast(s_axi_wlast),
    .m_axi_wvalid(s_axi_wvalid),
    .m_axi_wready(s_axi_wready),
    .m_axi_bid(s_axi_bid),
    .m_axi_bresp(s_axi_bresp),
    .m_axi_bvalid(s_axi_bvalid),
    .m_axi_bready(s_axi_bready),
    .m_axi_arid(s_axi_arid),
    .m_axi_araddr(s_axi_araddr),
    .m_axi_arlen(s_axi_arlen),
    .m_axi_arsize(s_axi_arsize),
    .m_axi_arburst(s_axi_arburst),
    .m_axi_arvalid(s_axi_arvalid),
    .m_axi_arready(s_axi_arready),
    .m_axi_rid(s_axi_rid),
    .m_axi_rdata(s_axi_rdata),
    .m_axi_rresp(s_axi_rresp),
    .m_axi_rlast(s_axi_rlast),
    .m_axi_rvalid(s_axi_rvalid),
    .m_axi_rready(s_axi_rready)
);

// Separate board modules: camera_capture -> framebuffer -> hdmi_display.
wire [1023:0] perf_snapshot;
wire perf_snapshot_valid;

wire [12:0] display_fifo_level;
wire [9:0] tmds_data0,tmds_data1,tmds_data2,tmds_clk;
// All calibration arithmetic is in the 50 MHz camera domain.
wire [10:0] wb_request_r,wb_request_b,wb_active_r,wb_active_b;
wire [3:0] wb_state;
style_wb_calibrator wb_calibrator(.clk(i_mipi_rx_pclk),.rst_n(camera_rst_n),
    .key_cal_n(key2_n),.key_restore_n(key3_n),.s_vs(w_mipi_rx_vs),
    .mean_valid(cfa_mean_valid),.mean_data(cfa_mean_data),
    .request_r(wb_request_r),.request_b(wb_request_b),
    .active_r(wb_active_r),.active_b(wb_active_b),.state(wb_state));

style_hdmi_display #(
    .RESERVE_CNN(1),.COLOR_PROBE(0),.CONTRAST_PROBE(1),
    .CONTRAST_INITIAL_LEVEL(0),.WB_OVERLAY(1),.PERF_OVERLAY(1)
) hdmi_display(
    .core_clk(core_clk),.core_rst_n(core_rst_n),.camera_clk(i_mipi_rx_pclk),.camera_rst_n(camera_rst_n),
    .pixel_clk(hdmi_tx_slow_clk),.pixel_rst_n(pixel_rst_n),.async_rst_n(w_arstn),
    .core_flush(display_flush),.core_front_valid(front_valid),.core_frame_id(front_id),.core_mode(mode),
    .capture_fps(capture_fps),.process_fps(process_fps),.bypass_active(bypass_active),
    .core_camera_frames(camera_frames_core),.core_drop_count(drop_count),.core_error_count(error_count),
    .s_rgb(display_rgb),.s_valid(display_valid),.s_ready(display_ready),
    .refresh_request(refresh_request),.refresh_ack(display_ack),.safe_window(safe_window),
    .raw_mean_valid(cfa_mean_valid),.raw_mean_data(cfa_mean_data),.key1_n(key1_n),
    .wb_state(wb_state),.wb_active_r(wb_active_r),.wb_active_b(wb_active_b),
    .perf_snapshot(perf_snapshot),.perf_snapshot_valid(perf_snapshot_valid),
    .video_rgb(video_rgb),.video_de(video_de),.video_hs(video_hs),.video_vs(video_vs),.video_x(video_x),.video_y(video_y),
    .tmds_data0(tmds_data0),.tmds_data1(tmds_data1),.tmds_data2(tmds_data2),.tmds_clk(tmds_clk),
    .underflows(underflows),.underflows_core(underflows_core),.fifo_level(display_fifo_level));
assign tmds_tx_clk_TX_DATA=~tmds_clk;
assign tmds_tx_data0_TX_DATA=~tmds_data0;
assign tmds_tx_data1_TX_DATA=~tmds_data1;
assign tmds_tx_data2_TX_DATA=~tmds_data2;
assign tmds_tx_clk_TX_OE=1'b1;assign tmds_tx_data0_TX_OE=1'b1;
assign tmds_tx_data1_TX_OE=1'b1;assign tmds_tx_data2_TX_OE=1'b1;
assign tmds_tx_clk_TX_RST=~pixel_rst_n;assign tmds_tx_data0_TX_RST=~pixel_rst_n;
assign tmds_tx_data1_TX_RST=~pixel_rst_n;assign tmds_tx_data2_TX_RST=~pixel_rst_n;
reg [25:0] heartbeat;
always @(posedge core_clk or negedge core_rst_n)
    if(!core_rst_n)heartbeat<=0;else heartbeat<=heartbeat+1'b1;
assign led={fatal_fault|camera_abort_fault,|error_count,front_valid,cal_done & heartbeat[24]};
// Unused DSI outputs are explicitly disabled; camera uses J5, monitor HDMI TX.
assign LCD_RST_P=1'b0;assign LCD_POWER=1'b0;
assign mipi_dp_clk_LP_P_OUT=0;
assign mipi_dp_clk_LP_N_OUT=0;
assign mipi_dp_clk_HS_OUT=0;
assign mipi_dp_clk_HS_OE=0;
assign mipi_dp_data3_LP_P_OUT=0;
assign mipi_dp_data2_LP_P_OUT=0;
assign mipi_dp_data1_LP_P_OUT=0;
assign mipi_dp_data0_LP_P_OUT=0;
assign mipi_dp_data3_LP_N_OUT=0;
assign mipi_dp_data2_LP_N_OUT=0;
assign mipi_dp_data1_LP_N_OUT=0;
assign mipi_dp_data0_LP_N_OUT=0;
assign mipi_dp_data0_HS_OUT=0;
assign mipi_dp_data1_HS_OUT=0;
assign mipi_dp_data2_HS_OUT=0;
assign mipi_dp_data3_HS_OUT=0;
assign mipi_dp_data3_HS_OE=0;
assign mipi_dp_data2_HS_OE=0;
assign mipi_dp_data1_HS_OE=0;
assign mipi_dp_data0_HS_OE=0;
assign mipi_dp_clk_RST=1'b1;
assign mipi_dp_data0_RST=1'b1;
assign mipi_dp_data1_RST=1'b1;
assign mipi_dp_data2_RST=1'b1;
assign mipi_dp_data3_RST=1'b1;
assign mipi_dp_clk_LP_P_OE=0;
assign mipi_dp_clk_LP_N_OE=0;
assign mipi_dp_data3_LP_P_OE=0;
assign mipi_dp_data3_LP_N_OE=0;
assign mipi_dp_data2_LP_P_OE=0;
assign mipi_dp_data2_LP_N_OE=0;
assign mipi_dp_data1_LP_P_OE=0;
assign mipi_dp_data1_LP_N_OE=0;
assign mipi_dp_data0_LP_P_OE=0;
assign mipi_dp_data0_LP_N_OE=0;
endmodule
