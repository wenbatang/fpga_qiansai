
/////////////////////////////////////////////////////////////////////////////
//
// Copyright (C) 2013-2021 Efinix Inc. All rights reserved.
//
// Description:
// Example top file for ti60f225 dev kit OOB design
//
// Language:  Verilog 2001
//
// ------------------------------------------------------------------------------

/////////////////////////////////////////////////////////////////////////////////
//`define SOFT_TAP 1
`include "ddr3_controller/ddr3_parameter.vh"
// `include "define.v"

module ti60f225_oob_top #(

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
  (* syn_peri_port = 0 *) input i_arstn,
  (* syn_peri_port = 0 *) input io_cam_scl_IN,
  (* syn_peri_port = 0 *) input io_cam_sda_IN,
  (* syn_peri_port = 0 *) input clk_100m,
  (* syn_peri_port = 0 *) input pll_locked,
  (* syn_peri_port = 0 *) input user_pll_locked,
  (* syn_peri_port = 0 *) input i_pll_locked,
  (* syn_peri_port = 0 *) input i_mipi_rx_pclk,
  (* syn_peri_port = 0 *) input fb,
  (* syn_peri_port = 0 *) input vid_clk_dvi2,
  (* syn_peri_port = 0 *) input pll_inst4_CLKOUT0,
  (* syn_peri_port = 0 *) input CLK_5M,
  (* syn_peri_port = 0 *) input i_mipi_tx_pclk,
  (* syn_peri_port = 0 *) input i_mipi_txc_sclk,
  (* syn_peri_port = 0 *) input core_clk,
  (* syn_peri_port = 0 *) input i_mipi_txd_sclk,
  (* syn_peri_port = 0 *) input CLK_25M,
  (* syn_peri_port = 0 *) input sdram_clk,
  (* syn_peri_port = 0 *) input tx_cal_clk_90edge,
  (* syn_peri_port = 0 *) input rx_cal_clk,
  (* syn_peri_port = 0 *) input tx_cal_clk,
  (* syn_peri_port = 0 *) input i_cam_ck_CLKOUT,
  (* syn_peri_port = 0 *) input jtag_inst1_CAPTURE,
  (* syn_peri_port = 0 *) input jtag_inst1_DRCK,
  (* syn_peri_port = 0 *) input jtag_inst1_RESET,
  (* syn_peri_port = 0 *) input jtag_inst1_RUNTEST,
  (* syn_peri_port = 0 *) input jtag_inst1_SEL,
  (* syn_peri_port = 0 *) input jtag_inst1_SHIFT,
  (* syn_peri_port = 0 *) input jtag_inst1_TCK,
  (* syn_peri_port = 0 *) input jtag_inst1_TDI,
  (* syn_peri_port = 0 *) input jtag_inst1_TMS,
  (* syn_peri_port = 0 *) input jtag_inst1_UPDATE,
  (* syn_peri_port = 0 *) input [15:0] ddr_dq_in_hi,
  (* syn_peri_port = 0 *) input [15:0] ddr_dq_in_lo,
  (* syn_peri_port = 0 *) input [1:0] ddr_dqs_in_hi,
  (* syn_peri_port = 0 *) input [1:0] ddr_dqs_in_lo,
  (* syn_peri_port = 0 *) input mipi_dp_data0_LP_N_IN,
  (* syn_peri_port = 0 *) input mipi_dp_data0_LP_P_IN,
 (* syn_peri_port = 0 *) input mipi_dp_data10_LP_N_IN,
  (* syn_peri_port = 0 *) input mipi_dp_data10_LP_P_IN,
  (* syn_peri_port = 0 *) input i_cam_ck_LP_N_IN,
  (* syn_peri_port = 0 *) input i_cam_ck_LP_P_IN,
  (* syn_peri_port = 0 *) input cam_d2_FIFO_EMPTY,
  (* syn_peri_port = 0 *) input [7:0] cam_d2_HS_IN,
  (* syn_peri_port = 0 *) input cam_d2_LP_N_IN,
  (* syn_peri_port = 0 *) input cam_d2_LP_P_IN,
  (* syn_peri_port = 0 *) input cam_d3_FIFO_EMPTY,
  (* syn_peri_port = 0 *) input [7:0] cam_d3_HS_IN,
  (* syn_peri_port = 0 *) input cam_d3_LP_N_IN,
  (* syn_peri_port = 0 *) input cam_d3_LP_P_IN,
  (* syn_peri_port = 0 *) input cam_d0_FIFO_EMPTY,
  (* syn_peri_port = 0 *) input [7:0] cam_d0_HS_IN,
  (* syn_peri_port = 0 *) input cam_d0_LP_N_IN,
  (* syn_peri_port = 0 *) input cam_d0_LP_P_IN,
  (* syn_peri_port = 0 *) input cam_d1_FIFO_EMPTY,
  (* syn_peri_port = 0 *) input [7:0] cam_d1_HS_IN,
  (* syn_peri_port = 0 *) input cam_d1_LP_N_IN,
  (* syn_peri_port = 0 *) input cam_d1_LP_P_IN,
  (* syn_peri_port = 0 *) output LCD_POWER,
  (* syn_peri_port = 0 *) output LCD_RST_P,
  (* syn_peri_port = 0 *) output io_cam_scl_OUT,
  (* syn_peri_port = 0 *) output io_cam_scl_OE,
  (* syn_peri_port = 0 *) output io_cam_sda_OUT,
  (* syn_peri_port = 0 *) output io_cam_sda_OE,
  (* syn_peri_port = 0 *) output [3:0] led,
  (* syn_peri_port = 0 *) output o_cam_rst_p,
  (* syn_peri_port = 0 *) output LCD_POWER1,
  (* syn_peri_port = 0 *) output LCD_RST_P1,
  (* syn_peri_port = 0 *) output DDR3_PLL_RSTN,
  (* syn_peri_port = 0 *) output [2:0] pll_shift,
  (* syn_peri_port = 0 *) output pll_shift_ena,
  (* syn_peri_port = 0 *) output [4:0] pll_shift_sel,
  (* syn_peri_port = 0 *) output USER_PLL_RSTN,
  (* syn_peri_port = 0 *) output pll_inst1_RSTN,
  (* syn_peri_port = 0 *) output jtag_inst1_TDO,
  (* syn_peri_port = 0 *) output [15:0] ddr_addr,
  (* syn_peri_port = 0 *) output [2:0] ddr_ba,
  (* syn_peri_port = 0 *) output ddr_cas_n,
  (* syn_peri_port = 0 *) output ddr_ck_hi,
  (* syn_peri_port = 0 *) output ddr_ck_lo,
  (* syn_peri_port = 0 *) output [0:0] ddr_cke,
  (* syn_peri_port = 0 *) output [0:0] ddr_cs_n,
  (* syn_peri_port = 0 *) output [1:0] ddr_dm_hi,
  (* syn_peri_port = 0 *) output [1:0] ddr_dm_lo,
  (* syn_peri_port = 0 *) output [15:0] ddr_dq_out_hi,
  (* syn_peri_port = 0 *) output [15:0] ddr_dq_out_lo,
  (* syn_peri_port = 0 *) output [15:0] ddr_dq_oe,
  (* syn_peri_port = 0 *) output [1:0] ddr_dqs_out_hi,
  (* syn_peri_port = 0 *) output [1:0] ddr_dqs_out_lo,
  (* syn_peri_port = 0 *) output [1:0] ddr_dqs_oe,
  (* syn_peri_port = 0 *) output [1:0] ddr_dqs_oe_n,
  (* syn_peri_port = 0 *) output [0:0] ddr_odt,
  (* syn_peri_port = 0 *) output ddr_ras_n,
  (* syn_peri_port = 0 *) output ddr_reset_n,
  (* syn_peri_port = 0 *) output ddr_we_n,
  (* syn_peri_port = 0 *) output mipi_dp_clk_HS_OE,
  (* syn_peri_port = 0 *) output [7:0] mipi_dp_clk_HS_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_clk_LP_N_OE,
  (* syn_peri_port = 0 *) output mipi_dp_clk_LP_N_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_clk_LP_P_OE,
  (* syn_peri_port = 0 *) output mipi_dp_clk_LP_P_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_clk_RST,
  (* syn_peri_port = 0 *) output mipi_dp_data0_HS_OE,
  (* syn_peri_port = 0 *) output [7:0] mipi_dp_data0_HS_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data0_LP_N_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data0_LP_N_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data0_LP_P_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data0_LP_P_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data0_RST,
  (* syn_peri_port = 0 *) output mipi_dp_data1_HS_OE,
  (* syn_peri_port = 0 *) output [7:0] mipi_dp_data1_HS_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data1_LP_N_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data1_LP_N_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data1_LP_P_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data1_LP_P_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data1_RST,
  (* syn_peri_port = 0 *) output mipi_dp_data2_HS_OE,
  (* syn_peri_port = 0 *) output [7:0] mipi_dp_data2_HS_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data2_LP_N_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data2_LP_N_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data2_LP_P_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data2_LP_P_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data2_RST,
  (* syn_peri_port = 0 *) output mipi_dp_data3_HS_OE,
  (* syn_peri_port = 0 *) output [7:0] mipi_dp_data3_HS_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data3_LP_N_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data3_LP_N_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data3_LP_P_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data3_LP_P_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data3_RST,
  (* syn_peri_port = 0 *) output o_cam_ck_HS_ENA,
  (* syn_peri_port = 0 *) output o_cam_ck_HS_TERM,
  (* syn_peri_port = 0 *) output cam_d2_FIFO_RD,
  (* syn_peri_port = 0 *) output cam_d2_HS_ENA,
  (* syn_peri_port = 0 *) output cam_d2_HS_TERM,
  (* syn_peri_port = 0 *) output cam_d2_RST,
  (* syn_peri_port = 0 *) output cam_d3_FIFO_RD,
  (* syn_peri_port = 0 *) output cam_d3_HS_ENA,
  (* syn_peri_port = 0 *) output cam_d3_HS_TERM,
  (* syn_peri_port = 0 *) output cam_d3_RST,
  (* syn_peri_port = 0 *) output cam_d0_FIFO_RD,
  (* syn_peri_port = 0 *) output cam_d0_HS_ENA,
  (* syn_peri_port = 0 *) output cam_d0_HS_TERM,
  (* syn_peri_port = 0 *) output cam_d0_RST,
  (* syn_peri_port = 0 *) output cam_d1_FIFO_RD,
  (* syn_peri_port = 0 *) output cam_d1_HS_ENA,
  (* syn_peri_port = 0 *) output cam_d1_HS_TERM,
  (* syn_peri_port = 0 *) output cam_d1_RST,
  (* syn_peri_port = 0 *) output mipi_dp_clk1_HS_OE,
  (* syn_peri_port = 0 *) output [7:0] mipi_dp_clk1_HS_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_clk1_LP_N_OE,
  (* syn_peri_port = 0 *) output mipi_dp_clk1_LP_N_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_clk1_LP_P_OE,
  (* syn_peri_port = 0 *) output mipi_dp_clk1_LP_P_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_clk1_RST,
  (* syn_peri_port = 0 *) output mipi_dp_data10_HS_OE,
  (* syn_peri_port = 0 *) output [7:0] mipi_dp_data10_HS_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data10_LP_N_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data10_LP_N_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data10_LP_P_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data10_LP_P_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data10_RST,
  (* syn_peri_port = 0 *) output mipi_dp_data11_HS_OE,
  (* syn_peri_port = 0 *) output [7:0] mipi_dp_data11_HS_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data11_LP_N_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data11_LP_N_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data11_LP_P_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data11_LP_P_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data11_RST,
  (* syn_peri_port = 0 *) output mipi_dp_data12_HS_OE,
  (* syn_peri_port = 0 *) output [7:0] mipi_dp_data12_HS_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data12_LP_N_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data12_LP_N_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data12_LP_P_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data12_LP_P_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data12_RST,
  (* syn_peri_port = 0 *) output mipi_dp_data13_HS_OE,
  (* syn_peri_port = 0 *) output [7:0] mipi_dp_data13_HS_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data13_LP_N_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data13_LP_N_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data13_LP_P_OE,
  (* syn_peri_port = 0 *) output mipi_dp_data13_LP_P_OUT,
  (* syn_peri_port = 0 *) output mipi_dp_data13_RST	


);



//===============================================================================
//localparam
//===============================================================================
localparam WR_FIFO_DEPTH  = 1024;
localparam RD_FIFO_DEPTH  = 1024;

localparam	MAX_HRES		= 12'd1920;
localparam	MAX_VRES		= 12'd1080;
localparam	HSP			= 8'd4;
localparam	HBP			= 8'd88;
localparam	HFP			= 8'd120;
localparam	VSP			= 8'd2;
localparam	VBP			= 8'd20;
localparam	VFP			= 8'd20;
//===============================================================================
//signal
//===============================================================================
   
wire                              app_sr_active;
wire                              app_ref_ack;
wire                              app_zq_ack;
wire                              cal_done;

// Slave Interface Write Address Ports
wire [AXI_ID_WIDTH-1:0]           s_axi_awid;
wire [AXI_ADDR_WIDTH-1:0]         s_axi_awaddr;
wire [7:0]                        s_axi_awlen;
wire [2:0]                        s_axi_awsize;
wire [1:0]                        s_axi_awburst;
wire [0:0]                        s_axi_awlock;
wire [3:0]                        s_axi_awcache;
wire [2:0]                        s_axi_awprot;
wire                              s_axi_awvalid;
wire                              s_axi_awready;
// Slave Interface Write Data Ports
wire [AXI_DATA_WIDTH-1:0]         s_axi_wdata;
wire [(AXI_DATA_WIDTH/8)-1:0]     s_axi_wstrb;
wire                              s_axi_wlast;
wire                              s_axi_wvalid;
wire                              s_axi_wready;
// Slave Interface Write Response Ports
wire                              s_axi_bready;
wire [AXI_ID_WIDTH-1:0]           s_axi_bid;
wire [1:0]                        s_axi_bresp;
wire                              s_axi_bvalid;
// Slave Interface Read Address Ports
wire [AXI_ID_WIDTH-1:0]           s_axi_arid;
wire [AXI_ADDR_WIDTH-1:0]         s_axi_araddr;
wire [7:0]                        s_axi_arlen;
wire [2:0]                        s_axi_arsize;
wire [1:0]                        s_axi_arburst;
wire [0:0]                        s_axi_arlock;
wire [3:0]                        s_axi_arcache;
wire [2:0]                        s_axi_arprot;
wire                              s_axi_arvalid;
wire                              s_axi_arready;
// Slave Interface Read Data Ports
wire                              s_axi_rready;
wire [AXI_ID_WIDTH-1:0]           s_axi_rid;
wire [AXI_DATA_WIDTH-1:0]         s_axi_rdata;
wire [1:0]                        s_axi_rresp;
wire                              s_axi_rlast;
wire                              s_axi_rvalid;




////////////////////////////////////////////////////////////////
// System & Debugger
wire    w_arstn;
wire	w_sysclk_mcu_arstn;
wire	w_sysclk_mcu_arst;
wire	w_mipi_rx_pclk_arstn;
wire	w_mipi_rx_pclk_arst;

wire		       w_mipi_rx_vs;
wire		       w_mipi_rx_hs;
wire	       w_mipi_rx_de;
wire	[63:0]			w_mipi_rx_data	;

wire					io_systemReset;



//===================================================================================================
//reset module
//===================================================================================================

assign w_arstn  		       = i_pll_locked & pll_locked & user_pll_locked;
assign pll_inst1_RSTN  		= i_arstn;
assign USER_PLL_RSTN      		= i_arstn;
assign mipi_dsi_tx_pll_RSTN 	= i_arstn;
assign DDR3_PLL_RSTN 		= i_arstn;
reset_ctrl
#(
	.NUM_RST		(2),
	.CYCLE			(1),
	.IN_RST_ACTIVE	(4'b00),
	.OUT_RST_ACTIVE	(4'b10)
)
inst_reset_ctrl
(
	.i_arst		({2{w_arstn}}),//({{4{i_pll_locked}},                  {2{i_arstn}}}),
	.i_clk			({2{i_mipi_rx_pclk}}),
	.o_srst		({w_mipi_rx_pclk_arst, w_mipi_rx_pclk_arstn})
);


reset_ctrl
#(
	.NUM_RST		(2),
	.CYCLE			(10),
	.IN_RST_ACTIVE	(2'b00),
	.OUT_RST_ACTIVE	(2'b10)
)
inst_reset_mcu_ctrl
(
	.i_arst		({2{w_arstn}}),
	.i_clk			({2{i_soc_clk}}),
	.o_srst		({w_sysclk_mcu_arst,w_sysclk_mcu_arstn})
);



reg [25:0] cnt = 'd0;
always @( posedge core_clk)
begin 
       cnt <= cnt + 1'b1;
end
assign led[0]  = cal_done ? cnt[24] : 1'b0;

//========================================================================================================
//MIPI RX
//========================================================================================================
wire i_mipi_clk ;
assign i_mipi_clk = core_clk;
assign i_soc_clk  = core_clk;

		assign	cam_d0_RST		= 1'b0;
		assign	cam_d1_RST		= 1'b0;
		assign  cam_d2_RST = 1'b0;
    assign  cam_d3_RST = 1'b0;
	
	
		

		csi_rx_controller inst_efx_csi2_rx
		(
              .reset_n			(i_arstn),
              .clk				(i_mipi_clk),
              .reset_byte_HS_n	(i_arstn),
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
              .irq				()
		);

    wire		       w1_mipi_rx_vs;
wire		       w1_mipi_rx_hs;
wire	       w1_mipi_rx_de;
wire	[39:0]			w1_mipi_rx_data	;
sensor_clipper  sensor_clipper_inst (
    .clk(i_mipi_rx_pclk),
    .i_vs(w_mipi_rx_vs),
    .i_hs(w_mipi_rx_hs),
    .i_de(w_mipi_rx_de),
    .i_dat(w_mipi_rx_data[39:0]),

    .o_hs(w1_mipi_rx_hs),
    .o_vs(w1_mipi_rx_vs),
    .o_de(w1_mipi_rx_de),
    .o_dat(w1_mipi_rx_data)
   
  );

//========================================================================================================
//
//========================================================================================================
		

//*************** imx219 config********************/
// mipi_config_imx219_top u_config_imx219(
// 										.i_sys_clk(CLK_5M)    	,    /////48M 
// 										.sys_rstn(vid_rst_n )    ,
// 										.o_sen_rst_n(o_cam_rstn)  	,
										
										// .o_iic_sda_OE(io_cam_sda_OE) ,
										// .i_iic_sda(io_cam_sda_IN)   	,
										// .o_iic_sda(io_cam_sda_OUT)   	,
										// .o_iic_scl(io_cam_scl)    	
										// ); 	

wire scl_padoen_o;
wire sda_padoen_o;


reg [12:0] i2c_rst_cnt = '0;

always @( posedge CLK_5M or negedge w_arstn )
begin
    if( !w_arstn )
       i2c_rst_cnt <= 'd0;
    else 
       i2c_rst_cnt <= i2c_rst_cnt[12] ? i2c_rst_cnt : i2c_rst_cnt + 1'b1;
end
wire i2c_rst_n = i2c_rst_cnt[12];

i2c_master_ctrl_top u2_i2c_master_ctrl_top(
  /*i*/.clk			(CLK_5M		),
  /*i*/.rst_n			(i2c_rst_n		),
  /*i*/.scl_pad_i     (io_cam_scl_IN),//(1'b1),
  /*o*/.scl_pad_o     (io_cam_scl_OUT),
  /*o*/.scl_padoen_o  (scl_padoen_o),
  /*i*/.sda_pad_i     (io_cam_sda_IN),
  /*o*/.sda_pad_o     (io_cam_sda_OUT),
  /*o*/.sda_padoen_o  (sda_padoen_o)
  
  );
assign o_cam_rst_p = ~w_arstn;
assign io_cam_scl_OE = ~scl_padoen_o;
assign io_cam_sda_OE = ~sda_padoen_o;

//=====================================================================================
//frame buffer
//=====================================================================================
wire [7:0] 	ch0_r;
wire [7:0]    ch0_g;
wire [7:0]    ch0_b;
wire ch0_vs;
wire ch0_hs;
wire ch0_de;

wire hs;
wire vs;
wire de;
wire [7:0] rgb_1,rgb_0;
wire [7:0] rgb_2,rgb_3;
wire pixel_data_en;

 

color_bar_rgb # (
    .DYN_EN(1'b1),
    .HS_POLORY(1'b1),
    .VS_POLORY(1'b1),
    .SYMBOL_WIDTH(8),
    .SYMBOL_NUM(1),
    .PAR_PIXEL_NUM(4),
    .HFP(HFP),
    .HST(HSP),
    .HACT(MAX_HRES),
    .HBP(HBP),
    .VFP(VFP),
    .VST(VSP),
    .VACT(MAX_VRES),
    .VBP(VBP),
    .TEST_MODE(2'd0)
  )
  color_bar_rgb_inst (
    .clk(vid_clk_dvi2),//(i_mipi_rx_pclk),
    .rst_n(pixel_data_en),
    .h_cnt(h_cnt),
    .v_cnt(v_cnt),
    .hs(hs),
    .vs(vs),
    .de(de),
    .o_vid_data({rgb_3,rgb_2,rgb_1,rgb_0})
  );


// IMX219
  frame_buffer #(
.I_VID_WIDTH         (32),
.O_VID_WIDTH         (16),
.START_ADDR          (32'h00000        ),
.AXI_DATA_WIDTH      ( AXI_DATA_WIDTH	),
.AXI_ADDR_WIDTH      ( AXI_ADDR_WIDTH	),
.WR_FIFO_DEPTH	      ( 1024		),    
.RD_FIFO_DEPTH 	      ( 1024 	),
.BURST_LEN  	       (127),
.FB_NUM	            (3),
.MAX_VID_WIDTH	    (960) ,
.MAX_VID_HIGHT	    (1080) 


)checker0(
       .axi_clk		(core_clk 	        ),
       .rst_n			(pixel_data_en),//(vid_rst_n   ),

/*i*/.i_clk			(i_mipi_rx_pclk      ),//(vid_clk_dvi2),//
/*i*/.i_vs			(w_mipi_rx_vs	),//(vs),//
/*i*/.i_de			(w_mipi_rx_de & w_mipi_rx_hs	),//(de),//
/*i*/.vin 		({w_mipi_rx_data[39:32],w_mipi_rx_data[29:22],w_mipi_rx_data[19:12],w_mipi_rx_data[9:2]}	),//	({rgb_3,rgb_2,rgb_1,rgb_0}),//
                     
/*i*/.o_clk			(vid_clk_dvi2),//(i_mipi_rx_pclk	),
/*i*/.o_hs    		(ch0_hs		),			
/*i*/.o_vs    		(ch0_vs		),			
/*i*/.o_de    		(ch0_de		),			
/*i*/.vout    		({ch0_g,ch0_b}	),//ch0_r,

/*i*/.H_FRONT_PORCH (HFP/2  		),//
/*i*/.H_SYNC 	 	    (HSP/2	 	),///2
/*i*/.H_VALID 	 	  (MAX_HRES/2     ),//		
/*i*/.H_BACK_PORCH	(HBP/2		),//		
/*i*/.V_FRONT_PORCH (VFP  		),//		
/*i*/.V_SYNC 	 	    (VSP 	 	),//		
/*i*/.V_VALID 	 	  (MAX_VRES     ),//		
/*i*/.V_BACK_PORCH	(VBP		),//		

       .awid			(s_axi_awid	),      
       .awaddr		(s_axi_awaddr	),
       .awlen			(s_axi_awlen	),
       .awsize		(s_axi_awsize	),
       .awburst		(s_axi_awburst),
       .awprot    (s_axi_awprot ),
       .awcache   (s_axi_awcache),
       .awlock		(s_axi_awlock	),
       .awvalid		(s_axi_awvalid),
       .awready		(s_axi_awready),

       .arid			(s_axi_arid	  ),
       .araddr		(s_axi_araddr	),
       .arlen			(s_axi_arlen	),
       .arsize		(s_axi_arsize	),
       .arburst 	(s_axi_arburst),

       .arprot    (s_axi_arprot ),
       .arcache   (s_axi_arcache),
       .arlock 		(s_axi_arlock	),
       .arvalid		(s_axi_arvalid),
       .arready		(s_axi_arready),

       .wdata			(s_axi_wdata	),
       .wstrb			(s_axi_wstrb	),
       .wlast			(s_axi_wlast	),
       .wvalid		(s_axi_wvalid	),
       .wready		(s_axi_wready	),


       .rid			  (s_axi_rid	),
       .rdata			(s_axi_rdata	),
       .rlast			(s_axi_rlast	),
       .rvalid 		(s_axi_rvalid	),
       .rready		(s_axi_rready	),
       .rresp			(s_axi_rresp	),

       .bid			  (s_axi_bid	),
       .bvalid		(s_axi_bvalid	),
       .bready	  (s_axi_bready	)
);


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

//***************************************************************************
// debayer
//***************************************************************************


wire        rgb_vs;
wire        rgb_hs;
wire        rgb_de;
wire        rgb_valid;
wire [47:0] rgb_datax2;


debayer_top_2to1 debayer_top
(
	.in_pclk		  (vid_clk_dvi2),//(i_mipi_rx_pclk ),
	.in_rstn		  (pixel_data_en),//(vid_rst_n	),
	
	.raw_vs_i		  (ch0_vs		      ),
	.raw_hs_i		  (ch0_hs		      ),
	.raw_de_i		  (ch0_de		      ),
	.raw_valid_i	(ch0_de	        ),
	.raw_datax4_i	({ch0_b,ch0_g}	),
	
	.rgb_vs_o		  (rgb_vs         ),
	.rgb_hs_o		  (rgb_hs         ),
	.rgb_de_o		  (rgb_de         ),
	.rgb_valid_o	(rgb_valid      ),
	.rgb_datax2_o (rgb_datax2     )//b,g,r,b,g,r
);


//==============================================================================
// MIPI DSI
//==============================================================================
// wire [47:0] dout;
// wire o_de;
// wire o_vs;
// wire o_hs;
	


// color_bar_rgb # (
//     .DYN_EN(1'b1),
//     .HS_POLORY(1'b1),
//     .VS_POLORY(1'b1),
//     .SYMBOL_WIDTH(8),
//     .SYMBOL_NUM(3),
//     .PAR_PIXEL_NUM(2),
//     .HFP(HFP),
//     .HST(HSP),
//     .HACT(MAX_HRES),
//     .HBP(HBP),
//     .VFP(VFP),
//     .VST(VSP),
//     .VACT(MAX_VRES),
//     .VBP(VBP),
//     .TEST_MODE(2'd1)
//   )
//   color_bar_rgb_inst (
//     .clk(vid_clk_dvi2),
//     .rst_n(pixel_data_en),
//     .h_cnt(h_cnt),
//     .v_cnt(v_cnt),
//     .hs(o_hs),
//     .vs(o_vs),
//     .de(o_de),
//     .o_vid_data(dout)
//   );

	

dsi_tx_top # (
    .HACT(MAX_HRES),
    .VACT(MAX_VRES),
    .HSP(HSP),
    .HBP(HBP),
    .HFP(HFP),
    .VSP(VSP),
    .VBP(VBP),
    .VFP(VFP)
  )
  dsi_tx_top_inst1 (
	.rst_n(w_arstn),
    .i_mipi_clk(i_mipi_clk),
    .i_mipi_tx_pclk(i_mipi_tx_pclk),
    .i_sysclk_div_2(vid_clk_dvi2),

   /*i*/.pixel_vs_i  (rgb_vs								),//(o_vs),                //
   /*i*/.pixel_hs_i  (rgb_hs								),//(o_hs),                //
   /*i*/.pixel_de_i  (rgb_de								),//(o_de),                //
   /*i*/.pixel_data_i({16'd0,rgb_datax2}	  ),//({16'd0,dout}),        //
   /*o*/.pixel_data_en(pixel_data_en),


    .mipi_dp_data0_LP_N_IN(mipi_dp_data0_LP_N_IN),
    .mipi_dp_data0_LP_P_IN(mipi_dp_data0_LP_P_IN),
    
    .LCD_POWER(LCD_POWER),
    .LCD_RST_P(LCD_RST_P),
    .mipi_dp_clk_HS_OE(mipi_dp_clk_HS_OE),
    .mipi_dp_clk_HS_OUT(mipi_dp_clk_HS_OUT),
    .mipi_dp_clk_LP_N_OE(mipi_dp_clk_LP_N_OE),
    .mipi_dp_clk_LP_N_OUT(mipi_dp_clk_LP_N_OUT),
    .mipi_dp_clk_LP_P_OE(mipi_dp_clk_LP_P_OE),
    .mipi_dp_clk_LP_P_OUT(mipi_dp_clk_LP_P_OUT),
    .mipi_dp_clk_RST(mipi_dp_clk_RST),
    .mipi_dp_data0_HS_OE(mipi_dp_data0_HS_OE),
    .mipi_dp_data0_HS_OUT(mipi_dp_data0_HS_OUT),
    .mipi_dp_data0_LP_N_OE(mipi_dp_data0_LP_N_OE),
    .mipi_dp_data0_LP_N_OUT(mipi_dp_data0_LP_N_OUT),
    .mipi_dp_data0_LP_P_OE(mipi_dp_data0_LP_P_OE),
    .mipi_dp_data0_LP_P_OUT(mipi_dp_data0_LP_P_OUT),
    
    .mipi_dp_data1_HS_OE(mipi_dp_data1_HS_OE),
    .mipi_dp_data1_HS_OUT(mipi_dp_data1_HS_OUT),
    .mipi_dp_data1_LP_N_OE(mipi_dp_data1_LP_N_OE),
    .mipi_dp_data1_LP_N_OUT(mipi_dp_data1_LP_N_OUT),
    .mipi_dp_data1_LP_P_OE(mipi_dp_data1_LP_P_OE),
    .mipi_dp_data1_LP_P_OUT(mipi_dp_data1_LP_P_OUT),
    
    .mipi_dp_data2_HS_OE(mipi_dp_data2_HS_OE),
    .mipi_dp_data2_HS_OUT(mipi_dp_data2_HS_OUT),
    .mipi_dp_data2_LP_N_OE(mipi_dp_data2_LP_N_OE),
    .mipi_dp_data2_LP_N_OUT(mipi_dp_data2_LP_N_OUT),
    .mipi_dp_data2_LP_P_OE(mipi_dp_data2_LP_P_OE),
    .mipi_dp_data2_LP_P_OUT(mipi_dp_data2_LP_P_OUT),
    
    .mipi_dp_data3_HS_OE(mipi_dp_data3_HS_OE),
    .mipi_dp_data3_HS_OUT(mipi_dp_data3_HS_OUT),
    .mipi_dp_data3_LP_N_OE(mipi_dp_data3_LP_N_OE),
    .mipi_dp_data3_LP_N_OUT(mipi_dp_data3_LP_N_OUT),
    .mipi_dp_data3_LP_P_OE(mipi_dp_data3_LP_P_OE),
    .mipi_dp_data3_LP_P_OUT(mipi_dp_data3_LP_P_OUT),
	  .mipi_dp_data0_RST(mipi_dp_data0_RST),
	  .mipi_dp_data1_RST(mipi_dp_data1_RST),
	  .mipi_dp_data2_RST(mipi_dp_data2_RST),
    .mipi_dp_data3_RST(mipi_dp_data3_RST)
  );


dsi_tx_top # (
    .HACT(MAX_HRES),
    .VACT(MAX_VRES),
    .HSP(HSP),
    .HBP(HBP),
    .HFP(HFP),
    .VSP(VSP),
    .VBP(VBP),
    .VFP(VFP)
  )
  dsi_tx_top_inst2 (
	.rst_n(w_arstn),
    .i_mipi_clk(i_mipi_clk),
    .i_mipi_tx_pclk(i_mipi_tx_pclk),
    .i_sysclk_div_2(vid_clk_dvi2),

   /*i*/.pixel_vs_i  (rgb_vs								),//(o_vs),                //
   /*i*/.pixel_hs_i  (rgb_hs								),//(o_hs),                //
   /*i*/.pixel_de_i  (rgb_de								),//(o_de),                //
   /*i*/.pixel_data_i({16'd0,rgb_datax2}	  ),//({16'd0,dout}),        //
   /*o*/.pixel_data_en(),


    .mipi_dp_data0_LP_N_IN(mipi_dp_data10_LP_N_IN),
    .mipi_dp_data0_LP_P_IN(mipi_dp_data10_LP_P_IN),
    
    .LCD_POWER(LCD_POWER1),
    .LCD_RST_P(LCD_RST_P1),
    .mipi_dp_clk_HS_OE      (mipi_dp_clk1_HS_OE),
    .mipi_dp_clk_HS_OUT     (mipi_dp_clk1_HS_OUT),
    .mipi_dp_clk_LP_N_OE    (mipi_dp_clk1_LP_N_OE),
    .mipi_dp_clk_LP_N_OUT   (mipi_dp_clk1_LP_N_OUT),
    .mipi_dp_clk_LP_P_OE    (mipi_dp_clk1_LP_P_OE),
    .mipi_dp_clk_LP_P_OUT   (mipi_dp_clk1_LP_P_OUT),
    .mipi_dp_clk_RST        (mipi_dp_clk1_RST),
    .mipi_dp_data0_HS_OE    (mipi_dp_data10_HS_OE),
    .mipi_dp_data0_HS_OUT   (mipi_dp_data10_HS_OUT),
    .mipi_dp_data0_LP_N_OE  (mipi_dp_data10_LP_N_OE),
    .mipi_dp_data0_LP_N_OUT (mipi_dp_data10_LP_N_OUT),
    .mipi_dp_data0_LP_P_OE  (mipi_dp_data10_LP_P_OE),
    .mipi_dp_data0_LP_P_OUT (mipi_dp_data10_LP_P_OUT),
    
    .mipi_dp_data1_HS_OE    (mipi_dp_data11_HS_OE),
    .mipi_dp_data1_HS_OUT   (mipi_dp_data11_HS_OUT),
    .mipi_dp_data1_LP_N_OE  (mipi_dp_data11_LP_N_OE),
    .mipi_dp_data1_LP_N_OUT (mipi_dp_data11_LP_N_OUT),
    .mipi_dp_data1_LP_P_OE  (mipi_dp_data11_LP_P_OE),
    .mipi_dp_data1_LP_P_OUT (mipi_dp_data11_LP_P_OUT),
    
    .mipi_dp_data2_HS_OE    (mipi_dp_data12_HS_OE),
    .mipi_dp_data2_HS_OUT   (mipi_dp_data12_HS_OUT),
    .mipi_dp_data2_LP_N_OE  (mipi_dp_data12_LP_N_OE),
    .mipi_dp_data2_LP_N_OUT (mipi_dp_data12_LP_N_OUT),
    .mipi_dp_data2_LP_P_OE  (mipi_dp_data12_LP_P_OE),
    .mipi_dp_data2_LP_P_OUT (mipi_dp_data12_LP_P_OUT),
    
    .mipi_dp_data3_HS_OE    (mipi_dp_data13_HS_OE),
    .mipi_dp_data3_HS_OUT   (mipi_dp_data13_HS_OUT),
    .mipi_dp_data3_LP_N_OE  (mipi_dp_data13_LP_N_OE),
    .mipi_dp_data3_LP_N_OUT (mipi_dp_data13_LP_N_OUT),
    .mipi_dp_data3_LP_P_OE  (mipi_dp_data13_LP_P_OE),
    .mipi_dp_data3_LP_P_OUT (mipi_dp_data13_LP_P_OUT),
	  .mipi_dp_data0_RST(mipi_dp_data10_RST),
	  .mipi_dp_data1_RST(mipi_dp_data11_RST),
	  .mipi_dp_data2_RST(mipi_dp_data12_RST),
    .mipi_dp_data3_RST(mipi_dp_data13_RST)
  );

endmodule
