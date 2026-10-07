`include "src/ddr3_controller/ddr3_parameter.vh"
// `include "define.v"
module TI60F225_MIPI_dsi #
(
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
	input	wire	i_arstn,
input	wire	i_sysclk,
input	wire	i_sysclk_div_2,
input	wire	i_pll_locked,

input	wire	i_mipi_clk,
input	wire	i_mipi_txc_sclk,
input	wire	i_mipi_txd_sclk,
input	wire	i_mipi_tx_pclk,
input	wire	i_mipi_tx_pll_locked,
input osc_clk,
output osc_en,
//hdmi rx
output 			HPD_N,
input 			HDMI_5V_N,
input 			FPGA_HDMI_SCL_IN,
input 			FPGA_HDMI_SDA_IN,
output 			FPGA_HDMI_SCL_OUT,
output 			FPGA_HDMI_SCL_OE,
output 			FPGA_HDMI_SDA_OUT,
output 			FPGA_HDMI_SDA_OE,
input 			hdmi_rx_fast_clk,
input 			hdmi_rx_slow_clk,
input       	hdmi_tx_fast_clk,
input 			hdmi_rx_clk_RX_DATA,
input [9:0] 	hdmi_rx_d0_RX_DATA,
input [9:0] 	hdmi_rx_d1_RX_DATA,
input [9:0] 	hdmi_rx_d2_RX_DATA,
output 			hdmi_rx_clk_RX_ENA,
output 			hdmi_rx_d0_RX_RST,
output 			hdmi_rx_d0_RX_ENA,
output 			hdmi_rx_d1_RX_RST,
output 			hdmi_rx_d1_RX_ENA,
output 			hdmi_rx_d2_RX_RST,
output 			hdmi_rx_d2_RX_ENA,   
input hdmi_rx_pll_LOCKED ,
output hdmi_rx_pll_RSTN,
//

output	wire	o_pll_rstn,
output	wire	o_mipi_pll_rstn,

output	wire	mipi_dp_clk_LP_P_OUT,
output	wire	mipi_dp_clk_LP_N_OUT,
output	wire	[7:0] 	mipi_dp_clk_HS_OUT,
output	wire	mipi_dp_clk_HS_OE,
output	wire	mipi_dp_data3_LP_P_OUT,
output	wire	mipi_dp_data2_LP_P_OUT,
output	wire	mipi_dp_data1_LP_P_OUT,
output	wire	mipi_dp_data0_LP_P_OUT,
output	wire	mipi_dp_data3_LP_N_OUT,
output	wire	mipi_dp_data2_LP_N_OUT,
output	wire	mipi_dp_data1_LP_N_OUT,
output	wire	mipi_dp_data0_LP_N_OUT,
output	wire	[7:0] 	mipi_dp_data0_HS_OUT,
output	wire	[7:0] 	mipi_dp_data1_HS_OUT,
output	wire	[7:0] 	mipi_dp_data2_HS_OUT,
output	wire	[7:0] 	mipi_dp_data3_HS_OUT,
output	wire	mipi_dp_data3_HS_OE,
output	wire	mipi_dp_data2_HS_OE,
output	wire	mipi_dp_data1_HS_OE,
output	wire	mipi_dp_data0_HS_OE,

output	wire	mipi_dp_clk_RST,
output	wire	mipi_dp_data0_RST,
output	wire	mipi_dp_data1_RST,
output	wire	mipi_dp_data2_RST,
output	wire	mipi_dp_data3_RST,
output	wire	mipi_dp_clk_LP_P_OE,
output	wire	mipi_dp_clk_LP_N_OE,
output	wire	mipi_dp_data3_LP_P_OE,
output	wire	mipi_dp_data3_LP_N_OE,
output	wire	mipi_dp_data2_LP_P_OE,
output	wire	mipi_dp_data2_LP_N_OE,
output	wire	mipi_dp_data1_LP_P_OE,
output	wire	mipi_dp_data1_LP_N_OE,
output	wire	mipi_dp_data0_LP_P_OE,
output	wire	mipi_dp_data0_LP_N_OE,

input  	wire	mipi_dp_data0_LP_P_IN,
input  	wire	mipi_dp_data0_LP_N_IN,
output  wire    LCD_POWER,
output	wire	LCD_RST_P,


// ddr3
output 								DDR3_PLL_RSTN,
input  								DDR3_PLL_LOCKED,
input                              core_clk,     // CORE CLK @ 100MHz
input                              sdram_clk,    // SDRAM CK @ 400MHz
input                              rx_cal_clk,   // SDRAM CK @ 400MHz
input                              tx_cal_clk,   // SDRAM CK @ 400MHz
input                              tx_cal_clk_90edge,   // SDRAM CK @ 400MHz
output [2:0]                       pll_shift,  
output [4:0]                       pll_shift_sel,
output                             pll_shift_ena,  
output [3:0] 					   led ,
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
output [ODT_WIDTH-1:0]             ddr_odt
);

function integer log2;
	input	integer	val;
	integer	i;
	begin
		log2 = 0;
		for (i=0; 2**i<val; i=i+1)
			log2 = i+1;
	end
endfunction

localparam	MAX_HRES		= 12'd1920;
localparam	MAX_VRES		= 12'd1080;
localparam	HSP				= 8'd2;
localparam	HBP				= 8'd88;
localparam	HFP				= 8'd120;
localparam	VSP				= 8'd2;
localparam	VBP				= 8'd20;
localparam	VFP				= 8'd20;



////////////////////////////////////////////////////////////////
// signal 

reg 	r_rstn_video;
reg		[25:0]	r_rst_cnt;

////////////////////////////////////////////////////////////////
// DSI Tx AXI
wire	[31:0]	w_axi_rdata;
wire			w_axi_awready;
wire			w_axi_wready;
wire			w_axi_arready;
wire			w_axi_rvalid;
wire			w_axi_bvalid;

wire	[6:0]	w_axi_awaddr;
wire			w_axi_awvalid;
wire	[31:0]	w_axi_wdata;
wire			w_axi_wvalid;
wire			w_axi_bready;
wire	[6:0]	w_axi_araddr;
wire			w_axi_arvalid;
wire			w_axi_rready;

wire			w_confdone;
wire 			rst_n ;
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


//***************************************************************************

wire                              idelay_ld       ;
wire                              mpr_rdlvl_dly   ;
wire  [7:0]                       wrlvl_dq_check  ;
wire  [7:0]                       rd_level_dqs_check;  
wire  [15:0]                      debug_fifo;  
wire  [15:0]                      overflow_fifo;  
wire  [6:0]                       init_cur_state;  
wire                              app_rdy;  
wire  							  axi_clk;						 


//============================================================================
//============================================================================



assign	o_pll_rstn 			= i_arstn;
assign	o_mipi_pll_rstn 	= i_arstn;
assign  DDR3_PLL_RSTN 		= i_arstn;
assign  LCD_POWER 			= i_arstn;
assign	mipi_dp_clk_RST		= ~i_arstn;
assign	mipi_dp_data0_RST	= ~i_arstn;
assign	mipi_dp_data1_RST	= ~i_arstn;
assign	mipi_dp_data2_RST	= ~i_arstn;
assign	mipi_dp_data3_RST	= ~i_arstn;


assign rst_n = i_pll_locked &  i_mipi_tx_pll_locked & DDR3_PLL_LOCKED ;
assign axi_clk = core_clk;

reg [15:0] rst_cnt = 'd0;
wire   	    sys_rst_n;
always @( posedge axi_clk or negedge rst_n )
begin
	if( !rst_n )
		rst_cnt <= 'd0;
	else 
		rst_cnt <= rst_cnt[15] ? rst_cnt : rst_cnt + 1'b1;
end
assign sys_rst_n = rst_cnt[15];

//===================================================================================
//hdmi_rx
//===================================================================================
assign osc_en = 1'b1;
assign hdmi_rx_clk_RX_ENA = 1'b1;

assign hdmi_rx_d0_RX_ENA = 1'b1; 
assign hdmi_rx_d1_RX_ENA = 1'b1;  
assign hdmi_rx_d2_RX_ENA = 1'b1; 
 

assign hdmi_rx_d0_RX_RST = 1'b0; 
assign hdmi_rx_d1_RX_RST = 1'b0;
assign hdmi_rx_d2_RX_RST = 1'b0;  

wire 			                      rx_hsync;	
wire 			                      rx_vsync;	
wire 			                      rx_de	 ;  
wire [7:0]                      rdata_in;	
wire [7:0]                      gdata_in;	
wire [7:0]                      bdata_in;

reg [22:0] wait_cnt;
wire hdmi_rst_n ;
//hdmi_rx_pll_LOCKED
always @( posedge osc_clk )
begin
		if( ~HPD_N )
				if( wait_cnt[22])
						wait_cnt <= wait_cnt;
				else
						wait_cnt <= wait_cnt + 1'b1;
		else
				wait_cnt <= 0;
end 

assign  hdmi_rx_pll_RSTN   = wait_cnt[22];

  rst_n_piple # (
    .DLY(3)
  )
  rst_n_hdmi_rx_slow_clk (
    .clk(hdmi_rx_slow_clk ),
    .rst_n_i( hdmi_rx_pll_LOCKED),
    .rst_n_o(hdmi_rst_n)
  );


	hdmi_rx u_hdmi_rx(
 /*i*/.cfg_clk(osc_clk),
 /*i*/.rst_n  (rst_n),
 /*i*/.hdmi_rx_5v_n(HDMI_5V_N),
 /*o*/.hdmi_rx_hpd_n(HPD_N),
 	/*i*/.scl_i		(FPGA_HDMI_SCL_IN), 
	/*o*/.scl_o		(FPGA_HDMI_SCL_OUT), 
	/*o*/.scl_oe	(FPGA_HDMI_SCL_OE),    
	/*i*/.sda_i		(FPGA_HDMI_SDA_IN), 
	/*o*/.sda_o		(FPGA_HDMI_SDA_OUT), 
	/*o*/.sda_oe	(FPGA_HDMI_SDA_OE) 
);    
dvi_decoder u_dvi_decoder(                                                        

/*i*/.pclk          (hdmi_rx_slow_clk),         // double rate pixel clock                
/*i*/.bdata        	(~hdmi_rx_d0_RX_DATA),       // Blue data in                           
/*i*/.gdata       	(~hdmi_rx_d1_RX_DATA),       // Green data in                          
/*i*/.rdata         (~hdmi_rx_d2_RX_DATA),       // Red data in                            
/*i*/.rst_n         (hdmi_rst_n          ),      // external reset input, e.g. reset button
/*o*/.reset         (					),        // rx reset                               
/*o*/.hsync         (rx_hsync	),                // hsync data                             
/*o*/.vsync         (rx_vsync	),                // vsync data                             
/*o*/.de            (rx_de		),                // data enable                            
/*o*/.red           (rdata_in	),                // pixel data out                         
/*o*/.green         (gdata_in	),                // pixel data out                         
/*o*/.blue          (bdata_in	)                 // pixel data out                         
                                                                                
   );    // pixel data out   


//===================================================================================
//color_bar
//===================================================================================
wire gen_vs;					
wire gen_de;	
wire gen_hs;			
wire [7:0] gen_rgb_r;
wire [7:0] gen_rgb_g;
wire [7:0] gen_rgb_b;

color_bar_rgb #(
  .HS_POLORY 		(1'b1		  ),
  .VS_POLORY 		(1'b1		  ),
  .H_FRONT_PORCH 	(HFP		  ),
  .H_SYNC 		    (HSP		  ),
  .H_VALID 		    (MAX_HRES	  ),
  .H_BACK_PORCH 	(HBP		  ),
  .V_FRONT_PORCH 	(VFP		  ),
  .V_SYNC 		    (VSP		  ),
  .V_VALID 		    (MAX_VRES	  ),
  .V_BACK_PORCH 	(VBP		  ),
  .TEST_MODE 		(2'd1     	  )
)u_color_bar_rgb_gen(
  /*i*/.clk	  (i_sysclk	),
  /*i*/.rst_n (vid_rst_n),
  /*o*/.hs	  (gen_hs	),
  /*o*/.vs	  (gen_vs	),
  /*o*/.de	  (gen_de	),
  /*o*/.rgb_r (gen_rgb_r), 
  /*o*/.rgb_g (gen_rgb_g), 
  /*o*/.rgb_b (gen_rgb_b)  
  
  );
//=====================================================================================
  //frame buffer
  //=====================================================================================
wire [7:0] 	ch0_r;
wire [7:0]    ch0_g;
wire [7:0]    ch0_b;
wire ch0_vs;
wire ch0_hs;
wire ch0_de;

frame_buffer #(
	.I_VID_WIDTH (24),
	.O_VID_WIDTH (24),
	.START_ADDR     (32'h00000        ),
	.AXI_DATA_WIDTH ( AXI_DATA_WIDTH	),
	.AXI_ADDR_WIDTH ( AXI_ADDR_WIDTH	),
	.WR_FIFO_DEPTH	( 1024		),    
	.RD_FIFO_DEPTH 	( 1024 	),
	.BURST_LEN  	  (127),
	.FB_NUM			  (3),
	.MAX_VID_WIDTH	(1920) ,
	.MAX_VID_HIGHT	(1080) 


	)checker0(
/*i*/.axi_clk		(axi_clk 				     		 ),
/*i*/.rst_n			(vid_rst_n            				),

/*i*/.i_clk			(hdmi_rx_slow_clk	),				//(i_sysclk   				    	),//
/*i*/.i_vs			(rx_vsync	),						//(gen_vs						        ),//
/*i*/.i_de			(rx_de		),						//(gen_de						        ),//
/*i*/.vin 			({rdata_in,gdata_in,bdata_in}	),	//({gen_rgb_r,gen_rgb_g,gen_rgb_b}	),//
														  
/*i*/.o_clk			(i_sysclk	 			),		     
/*i*/.o_hs    		(ch0_hs					),			
/*i*/.o_vs    		(ch0_vs					),			
/*i*/.o_de    		(ch0_de					),			
/*i*/.vout    		({ch0_r,ch0_g,ch0_b}	),//

/*i*/.H_FRONT_PORCH (HFP  			),//
/*i*/.H_SYNC 	 	(HSP 	 		),//
/*i*/.H_VALID 	 	(MAX_HRES 		),//		
/*i*/.H_BACK_PORCH	(HBP			),//		
/*i*/.V_FRONT_PORCH (VFP  			),//		
/*i*/.V_SYNC 	 	(VSP 	 		),//		
/*i*/.V_VALID 	 	(MAX_VRES 		),//		
/*i*/.V_BACK_PORCH	(VBP			),//		

	.awid			(s_axi_awid		),      
	.awaddr			(s_axi_awaddr	),
	.awlen			(s_axi_awlen	),
	.awsize			(s_axi_awsize	),
	.awburst		(s_axi_awburst	),
	.awprot     	(s_axi_awprot 	),
	.awcache    	(s_axi_awcache	),
	.awlock			(s_axi_awlock	),
	.awvalid		(s_axi_awvalid	),
	.awready		(s_axi_awready	),

	.arid			(s_axi_arid		),
	.araddr			(s_axi_araddr	),
	.arlen			(s_axi_arlen	),
	.arsize			(s_axi_arsize	),
	.arburst 		(s_axi_arburst	),

	.arprot     	(s_axi_arprot 	),
	.arcache    	(s_axi_arcache	),
	.arlock 		(s_axi_arlock 	),
	.arvalid		(s_axi_arvalid	),
	.arready		(s_axi_arready	),

	.wdata			(s_axi_wdata	),
	.wstrb			(s_axi_wstrb	),
	.wlast			(s_axi_wlast	),
	.wvalid			(s_axi_wvalid	),
	.wready			(s_axi_wready	),


	.rid			(s_axi_rid		),
	.rdata			(s_axi_rdata	),
	.rlast			(s_axi_rlast	),
	.rvalid 		(s_axi_rvalid	),
	.rready			(s_axi_rready	),
	.rresp			(s_axi_rresp	),

	.bid			(s_axi_bid		),
	.bvalid			(s_axi_bvalid	),
	.bready			(s_axi_bready	)
		);
	  

ddr3_top                 u_ddr3_top
      (

    .axi_clk                (axi_clk             ),
    .core_clk               (core_clk            ),
    .sdram_clk              (sdram_clk           ),  
    .rx_cal_clk             (rx_cal_clk          ),
    .tx_cal_clk             (tx_cal_clk          ),
    .tx_cal_clk_90edge      (tx_cal_clk_90edge   ),
    .rstn                   (sys_rst_n           ),      
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


	
  vid_check  vid_check_inst (
    .clk(i_sysclk),
    .rst_n(vid_rst_n),
    .i_hs(ch0_hs),
    .i_vs(ch0_vs),
    .i_de(ch0_de),
    .vin({ch0_r,ch0_g,ch0_b}),
    .check_fail(check_fail)
  );

//===========================================================================
// MIPI DSI
//===========================================================================
always@(posedge i_mipi_clk or  negedge rst_n)
begin
	if ( !rst_n ) begin
		r_rst_cnt	<= 'd0;
	end else if(~r_rst_cnt[25]) begin		
		r_rst_cnt	<= r_rst_cnt + 1'b1;
			
	end
end
assign	LCD_RST_P	= ~rst_n;//r_rst_cnt[25];
wire axi_rst_n = r_rst_cnt[25];

reg [26:0] dly_cnt = 'd0;

// wire vid_rst_n;
always @( posedge i_sysclk_div_2 or negedge rst_n )
begin
	if( !rst_n )
		dly_cnt <= 'd0;
	else if( w_confdone )
		dly_cnt <= dly_cnt[26] ? dly_cnt :(dly_cnt + 1'b1);
	else 
		dly_cnt <= 'd0;
end 

assign vid_rst_n = dly_cnt[26];//sys_rst_n

// Panel driver initialization
panel_config
#(
	.INITIAL_CODE	("Panel_1080p_reg.mem"),
	.REG_DEPTH		(9'd150)
)
inst_panel_config
(
	.i_axi_clk		(i_mipi_clk		),
	.i_restn		(axi_rst_n),//(LCD_RST_P	),
	
	.i_axi_awready	(w_axi_awready	),
	.i_axi_wready	(w_axi_wready	),
	.i_axi_bvalid	(w_axi_bvalid	),
	.o_axi_awaddr	(w_axi_awaddr	),
	.o_axi_awvalid	(w_axi_awvalid	),
	.o_axi_wdata	(w_axi_wdata	),
	.o_axi_wvalid	(w_axi_wvalid	),
	.o_axi_bready	(w_axi_bready	),
	
	.i_axi_arready	(w_axi_arready	),
	.i_axi_rdata	(w_axi_rdata	),
	.i_axi_rvalid	(w_axi_rvalid	),
	.o_axi_araddr	(w_axi_araddr	),
	.o_axi_arvalid	(w_axi_arvalid	),
	.o_axi_rready	(w_axi_rready	),
	
	.o_addr_cnt		(			),
	.o_state		(			),
	.o_confdone		(w_confdone	),
	
	.i_dbg_we		(0	),
	.i_dbg_din		(0	),
	.i_dbg_addr		(0	),
	.o_dbg_dout		(	),
	.i_dbg_reconfig	(0	)
);


wire hs;
wire vs;
wire de;
wire [7:0] r_data;
wire [7:0] g_data;
wire [7:0] b_data;
wire [47:0] dout;
wire o_de;
wire o_vs;
wire o_hs;
	// color_bar_rgb #(
	// .HS_POLORY 		(1'b1	),
	// .VS_POLORY 		(1'b1	),
	// .H_FRONT_PORCH 	(HFP	),///2
	// .H_SYNC 		(HSP	),///2
	// .H_VALID 		(MAX_HRES	),///2
	// .H_BACK_PORCH 	(HBP		),///2
	// .V_FRONT_PORCH 	(VFP		),
	// .V_SYNC 		(VSP		),
	// .V_VALID 		(MAX_VRES	),
	// .V_BACK_PORCH 	(VBP		),
	// .TEST_MODE 		(2'd2		)
	// )u_color_bar_rgb(
	// /*i*/.clk	(i_sysclk),
	// /*i*/.rst_n	(vid_rst_n),
	// /*o*/.hs	(hs),
	// /*o*/.vs	(vs),
	// /*o*/.de	(de),
	// /*o*/.rgb_r	(r_data),    //像素数据、红色分量
	// /*o*/.rgb_g	(g_data),    //像素数据、绿色分量
	// /*o*/.rgb_b (b_data)    //像素数据、蓝色分量
	
	// );

	pixcel_122 # (
		.DIN(24),
		.PAR_WIDTH(2)
	  )
	  pixcel_122_inst (
		.wrclk(i_sysclk),
		.rdclk(i_sysclk_div_2),
		.rst_n(vid_rst_n),
		.din({ch0_b,ch0_g,ch0_r}),//({r_data,g_data,b_data}),//
		.i_hs(ch0_hs),//(hs),//
		.i_vs(ch0_vs),//(vs),//
		.i_de(ch0_de),//(de),//
		.dout(dout),
		.o_hs(o_hs),
		.o_vs(o_vs),
		.o_de(o_de)
	  );
	


// MIPI DSI TX Channel
dsi_tx
#(
)
inst_efx_dsi_tx
(
	.reset_n			(rst_n	),//(LCD_RST_P),//
	.clk				(i_mipi_clk		),	// 100
	.reset_byte_HS_n	(rst_n	),//(LCD_RST_P),//
	.clk_byte_HS		(i_mipi_tx_pclk	),	// 1000/8=125
	.reset_pixel_n		(rst_n	),//(vid_rst_n	)(LCD_RST_P),//
	.clk_pixel			(i_sysclk_div_2	),  // 1000/16=62.5
	// LVDS clock lane   
	.Tx_LP_CLK_P		(mipi_dp_clk_LP_P_OUT),
	.Tx_LP_CLK_P_OE     (mipi_dp_clk_LP_P_OE),
	.Tx_LP_CLK_N		(mipi_dp_clk_LP_N_OUT),
	.Tx_LP_CLK_N_OE     (mipi_dp_clk_LP_N_OE),
	.Tx_HS_C            (mipi_dp_clk_HS_OUT),
	.Tx_HS_enable_C		(mipi_dp_clk_HS_OE),
	
	// ----- DLane -----------
	// LVDS data lane
	.Tx_LP_D_P			({mipi_dp_data3_LP_P_OUT, mipi_dp_data2_LP_P_OUT, mipi_dp_data1_LP_P_OUT, mipi_dp_data0_LP_P_OUT}),
	.Tx_LP_D_P_OE       ({mipi_dp_data3_LP_P_OE, mipi_dp_data2_LP_P_OE, mipi_dp_data1_LP_P_OE, mipi_dp_data0_LP_P_OE}),
	.Tx_LP_D_N			({mipi_dp_data3_LP_N_OUT, mipi_dp_data2_LP_N_OUT, mipi_dp_data1_LP_N_OUT, mipi_dp_data0_LP_N_OUT}),
	.Tx_LP_D_N_OE       ({mipi_dp_data3_LP_N_OE, mipi_dp_data2_LP_N_OE, mipi_dp_data1_LP_N_OE, mipi_dp_data0_LP_N_OE}),
	.Tx_HS_D_0			(mipi_dp_data0_HS_OUT),
	.Tx_HS_D_1			(mipi_dp_data1_HS_OUT),
	.Tx_HS_D_2			(mipi_dp_data2_HS_OUT),
	.Tx_HS_D_3			(mipi_dp_data3_HS_OUT),
	// control signal to LVDS IO
	.Tx_HS_enable_D		({mipi_dp_data3_HS_OE, mipi_dp_data2_HS_OE, mipi_dp_data1_HS_OE, mipi_dp_data0_HS_OE}),
	.Rx_LP_D_P			(mipi_dp_data0_LP_P_IN),
	.Rx_LP_D_N			(mipi_dp_data0_LP_N_IN),
	
	//AXI4-Lite Interface
	.axi_clk		(i_mipi_clk		), 
	.axi_reset_n	(axi_rst_n),//(LCD_RST_P			),//
	.axi_awaddr		(w_axi_awaddr	),//Write Address. byte address.
	.axi_awvalid	(w_axi_awvalid	),//Write address valid.
	.axi_awready	(w_axi_awready	),//Write address ready.
	.axi_wdata		(w_axi_wdata	),//Write data bus.
	.axi_wvalid		(w_axi_wvalid	),//Write valid.
	.axi_wready		(w_axi_wready	),//Write ready.
						  
	.axi_bvalid		(w_axi_bvalid	),//Write response valid.
	.axi_bready		(w_axi_bready	),//Response ready.      
	.axi_araddr		(w_axi_araddr	),//Read address. byte address.
	.axi_arvalid	(w_axi_arvalid	),//Read address valid.
	.axi_arready	(w_axi_arready	),//Read address ready.
	.axi_rdata		(w_axi_rdata	),//Read data.
	.axi_rvalid		(w_axi_rvalid	),//Read valid.
	.axi_rready		(w_axi_rready	),//Read ready.

    .hsync				(o_hs),//(),
    .vsync				(o_vs),//(~w_pack_vs),
	.vc					(2'b0					),
	.datatype			(6'h3E					),
    .pixel_data			({16'd0,dout}			),//({16'b0, w_pack_data}),
    .pixel_data_valid	(o_de),//(w_pack_valid),
	.haddr				(MAX_HRES				),
	.TurnRequest_dbg    (1'b0					),
	.TurnRequest_done	(),
	.irq				()
);

endmodule
