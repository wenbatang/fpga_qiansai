
module TI60F225_MIPI_dsi
#(
    //RX parameters
    parameter tLPX_NS = 50,
    parameter tCLK_TERM_EN_NS = 38,
    parameter tD_TERM_EN_NS = 35,
    parameter tHS_SETTLE_NS = 85,
    parameter tHS_PREPARE_ZERO_NS = 145,
    parameter HS_BYTECLK_MHZ = 125,
    parameter CLOCK_FREQ_MHZ = 100,
    parameter NUM_DATA_LANE = 4,
    parameter ENABLE_USER_DESKEWCAL = 0,
    parameter DPHY_CLOCK_MODE = "Continuous",
    parameter ENABLE_BIDIR = 1,
    
    //TX parameters
    parameter tLP_EXIT_NS = 100,
    parameter BTA_TIMEOUT_NS = 100000,
    parameter tHS_PREPARE_NS = 40,
    parameter tWAKEUP_NS = 1000,
    parameter tHS_EXIT_NS = 100,      
    parameter tHS_ZERO_NS = 105,     
    parameter tHS_TRAIL_NS = 60,
    
    parameter tINIT_NS = 100000,
    parameter PACK_TYPE = 2'b11,
//    parameter AREGISTER = 8,
    parameter PACKET_SEQUENCES = 1,
    parameter PIXEL_FIFO_DEPTH = 2048,
    parameter HS_CMD_FIFO_DEPTH = 128,
    parameter LP_CMD_FIFO_DEPTH = 128,
    parameter LP_CMD_RDATAFIFO_DEPTH = 128,

    parameter MAX_HRES  = 11'd1080  ,
    parameter MAX_VRES  = 11'd1920  ,
    parameter HSP       = 10'd100   ,
    parameter HBP       = 10'd100   ,
    parameter HFP       = 10'd250   ,
    parameter VSP       = 10'd3     ,    
    parameter VBP       = 10'd5     ,
    parameter VFP       = 11'd6
)(
    i_arstn,
    i_fb_clk,
    i_sysclk,
    // i_sysclk_div_2,
    i_pll_locked,
    
    i_mipi_clk,
    i_mipi_tx_pclk,
    i_mipi_tx_pll_locked,

    o_lcd_rstn,
    o_pll_rstn,
    o_mipi_pll_rstn,

    i_inject_err,
    led,

///////Tx interface 1///////////    

    mipi_dp_clk_LP_P_OUT,
    mipi_dp_clk_LP_N_OUT,
    mipi_dp_clk_HS_OUT,
    mipi_dp_clk_HS_OE,
    mipi_dp_data0_LP_P_OUT,
    mipi_dp_data1_LP_P_OUT,
    mipi_dp_data2_LP_P_OUT, 
    mipi_dp_data3_LP_P_OUT,
    
    mipi_dp_data0_LP_P_OE,
    mipi_dp_data1_LP_P_OE,
    mipi_dp_data2_LP_P_OE,
    mipi_dp_data3_LP_P_OE,
    
    mipi_dp_clk_RST,
    mipi_dp_data0_RST,
    mipi_dp_data1_RST,
    mipi_dp_data2_RST,
    mipi_dp_data3_RST,
    mipi_dp_clk_LP_P_OE,
    mipi_dp_clk_LP_N_OE,
    
    mipi_dp_data0_LP_N_OUT,
    mipi_dp_data1_LP_N_OUT,
    mipi_dp_data2_LP_N_OUT,
    mipi_dp_data3_LP_N_OUT,
    
    mipi_dp_data0_LP_N_OE,
    mipi_dp_data1_LP_N_OE,
    mipi_dp_data2_LP_N_OE,
    mipi_dp_data3_LP_N_OE,
    
    mipi_dp_data0_HS_OUT,
    mipi_dp_data1_HS_OUT,
    mipi_dp_data2_HS_OUT,
    mipi_dp_data3_HS_OUT,
    
    mipi_dp_data0_HS_OE,
    mipi_dp_data1_HS_OE,
    mipi_dp_data2_HS_OE,
    mipi_dp_data3_HS_OE,
    
    mipi_dp_data0_LP_P_IN,
    mipi_dp_data0_LP_N_IN,

/////////Rx interface///////////    
    mipi_rx_clk_CLKOUT,
    mipi_rx_clk_LP_P_IN,
    mipi_rx_clk_LP_N_IN,
    mipi_rx_clk_HS_ENA,
    mipi_rx_clk_HS_TERM,
    mipi_rx_data0_LP_P_IN,
    mipi_rx_data0_LP_N_IN,
    mipi_rx_data1_LP_P_IN,
    mipi_rx_data1_LP_N_IN,
    mipi_rx_data2_LP_P_IN,
    mipi_rx_data2_LP_N_IN,
    mipi_rx_data3_LP_P_IN,
    mipi_rx_data3_LP_N_IN,
    mipi_rx_data0_HS_IN,
    mipi_rx_data1_HS_IN,
    mipi_rx_data2_HS_IN,
    mipi_rx_data3_HS_IN,
    mipi_rx_data0_HS_ENA,   
    mipi_rx_data1_HS_ENA,
    mipi_rx_data2_HS_ENA,
    mipi_rx_data3_HS_ENA,           
    mipi_rx_data0_HS_TERM,
    mipi_rx_data1_HS_TERM,
    mipi_rx_data2_HS_TERM,
    mipi_rx_data3_HS_TERM,
    mipi_rx_data0_FIFO_RD,
    mipi_rx_data1_FIFO_RD,
    mipi_rx_data2_FIFO_RD,
    mipi_rx_data3_FIFO_RD,                         
    mipi_rx_data0_FIFO_EMPTY,
    mipi_rx_data1_FIFO_EMPTY,
    mipi_rx_data2_FIFO_EMPTY,
    mipi_rx_data3_FIFO_EMPTY,
    mipi_rx_data0_LP_P_OUT,
    mipi_rx_data0_LP_P_OE,
    mipi_rx_data0_LP_N_OUT,
    mipi_rx_data0_LP_N_OE, 
    mipi_rx_data0_RST,
    mipi_rx_data1_RST,
    mipi_rx_data2_RST,
    mipi_rx_data3_RST
);

input   wire    i_arstn;
input   wire    i_fb_clk;
input   wire    i_sysclk;
// input    wire    i_sysclk_div_2;
input   wire    i_pll_locked;

input   wire    i_mipi_clk;
input   wire    i_mipi_tx_pclk;
input   wire    i_mipi_tx_pll_locked;

output  wire    o_lcd_rstn;
output  wire    o_pll_rstn;
output  wire    o_mipi_pll_rstn;

input   wire    i_inject_err;
output  wire    [3:0] led;

output  wire    mipi_dp_clk_LP_P_OUT;
output  wire    mipi_dp_clk_LP_N_OUT;
output  wire    [7:0]   mipi_dp_clk_HS_OUT;
output  wire    mipi_dp_clk_HS_OE;
output  wire    mipi_dp_data3_LP_P_OUT;
output  wire    mipi_dp_data2_LP_P_OUT;
output  wire    mipi_dp_data1_LP_P_OUT;
output  wire    mipi_dp_data0_LP_P_OUT;
output  wire    mipi_dp_data3_LP_N_OUT;
output  wire    mipi_dp_data2_LP_N_OUT;
output  wire    mipi_dp_data1_LP_N_OUT;
output  wire    mipi_dp_data0_LP_N_OUT;
output  wire    [7:0]   mipi_dp_data0_HS_OUT;
output  wire    [7:0]   mipi_dp_data1_HS_OUT;
output  wire    [7:0]   mipi_dp_data2_HS_OUT;
output  wire    [7:0]   mipi_dp_data3_HS_OUT;
output  wire    mipi_dp_data3_HS_OE;
output  wire    mipi_dp_data2_HS_OE;
output  wire    mipi_dp_data1_HS_OE;
output  wire    mipi_dp_data0_HS_OE;

output  wire    mipi_dp_clk_RST;
output  wire    mipi_dp_data0_RST;
output  wire    mipi_dp_data1_RST;
output  wire    mipi_dp_data2_RST;
output  wire    mipi_dp_data3_RST;
output  wire    mipi_dp_clk_LP_P_OE;
output  wire    mipi_dp_clk_LP_N_OE;
output  wire    mipi_dp_data3_LP_P_OE;
output  wire    mipi_dp_data3_LP_N_OE;
output  wire    mipi_dp_data2_LP_P_OE;
output  wire    mipi_dp_data2_LP_N_OE;
output  wire    mipi_dp_data1_LP_P_OE;
output  wire    mipi_dp_data1_LP_N_OE;
output  wire    mipi_dp_data0_LP_P_OE;
output  wire    mipi_dp_data0_LP_N_OE;
input   wire    mipi_dp_data0_LP_P_IN;
input   wire    mipi_dp_data0_LP_N_IN;


/////MIPI RX////////
input wire              mipi_rx_clk_CLKOUT; 
    // LVDS clock lane   
input wire              mipi_rx_clk_LP_P_IN; 
input wire              mipi_rx_clk_LP_N_IN;
output wire             mipi_rx_clk_HS_ENA; 
output wire             mipi_rx_clk_HS_TERM;
    // LVDS RX data lane
input wire              mipi_rx_data0_LP_P_IN;
input wire              mipi_rx_data0_LP_N_IN;
input wire              mipi_rx_data1_LP_P_IN;
input wire              mipi_rx_data1_LP_N_IN;
input wire              mipi_rx_data2_LP_P_IN;
input wire              mipi_rx_data2_LP_N_IN;
input wire              mipi_rx_data3_LP_P_IN;
input wire              mipi_rx_data3_LP_N_IN;

input wire  [7:0]       mipi_rx_data0_HS_IN;
input wire  [7:0]       mipi_rx_data1_HS_IN;
input wire  [7:0]       mipi_rx_data2_HS_IN;
input wire  [7:0]       mipi_rx_data3_HS_IN;

    // control signal to LVDS IO
output wire             mipi_rx_data0_HS_ENA;   
output wire             mipi_rx_data1_HS_ENA;
output wire             mipi_rx_data2_HS_ENA;
output wire             mipi_rx_data3_HS_ENA;           
output wire             mipi_rx_data0_HS_TERM;
output wire             mipi_rx_data1_HS_TERM;
output wire             mipi_rx_data2_HS_TERM;
output wire             mipi_rx_data3_HS_TERM;
output wire             mipi_rx_data0_FIFO_RD;
output wire             mipi_rx_data1_FIFO_RD;
output wire             mipi_rx_data2_FIFO_RD;
output wire             mipi_rx_data3_FIFO_RD;                         
input wire              mipi_rx_data0_FIFO_EMPTY;
input wire              mipi_rx_data1_FIFO_EMPTY;
input wire              mipi_rx_data2_FIFO_EMPTY;
input wire              mipi_rx_data3_FIFO_EMPTY;
    //Bidir mode interface ports
output wire             mipi_rx_data0_LP_P_OUT;
output wire             mipi_rx_data0_LP_P_OE;
output wire             mipi_rx_data0_LP_N_OUT;
output wire             mipi_rx_data0_LP_N_OE;

output wire             mipi_rx_data0_RST;
output wire             mipi_rx_data1_RST;
output wire             mipi_rx_data2_RST;
output wire             mipi_rx_data3_RST;

/////////////////////////////////////

assign  mipi_dp_clk_RST     = ~i_arstn;
assign  mipi_dp_data0_RST   = ~i_arstn;
assign  mipi_dp_data1_RST   = ~i_arstn;
assign  mipi_dp_data2_RST   = ~i_arstn;
assign  mipi_dp_data3_RST   = ~i_arstn;

assign  o_pll_rstn = i_arstn;
assign  o_mipi_pll_rstn = i_arstn;


////////////////////////////////////////////////////////////////
// System & Debugger
wire    w_sysclk_arstn;
wire    w_sysclk_arst;
wire    w_sys_dp_arstn;
wire    w_sys_dp_arst;

reg     r_rstn_video;
reg     [19:0]  r_rst_cnt;
reg     r_lcd_rstn;

////////////////////////////////////////////////////////////////
// DSI Tx AXI
wire    [31:0]  w_axi_rdata;
wire    w_axi_awready;
wire    w_axi_wready;
wire    w_axi_arready;
wire    w_axi_rvalid;
wire    w_axi_bvalid;

wire    [6:0]   w_axi_awaddr;
wire    w_axi_awvalid;
wire    [31:0]  w_axi_wdata;
wire    w_axi_wvalid;
wire    w_axi_bready;
wire    [6:0]   w_axi_araddr;
wire    w_axi_arvalid;
wire    w_axi_rready;

// wire w_confdone;

////////Rx to Tx2//////////
wire    hsync;
wire    vsync;
wire [1:0]    vc;
wire [15:0]   word_count;
wire [63:0]   pixel_data;
wire    pixel_data_valid;
wire [5:0]    datatype;
/////////////////////////////

wire    i_rstn; //not used
wire    [11:0]w_vga_x;
wire    [11:0]w_vga_y;
wire    w_vga_hs;
wire    w_vga_vs;
wire    w_vga_de;
wire    w_vga_valid;

wire    [11:0]w_pg_x;
wire    [11:0]w_pg_y;
wire    w_pg_valid;
wire    w_pg_de;
wire    w_pg_hs;
wire    w_pg_vs;
wire    [7:0]w_pg_data_R;
wire    [7:0]w_pg_data_G;
wire    [7:0]w_pg_data_B;

wire    [11:0]w_pack_x;
wire    [11:0]w_pack_y;
wire    w_pack_valid;
wire    w_pack_de;
wire    w_pack_hs;
wire    w_pack_vs;
wire    [47:0]w_pack_data;

reg     [15:0]r_led_cnt;
reg     r_pack_vs_1P;
reg     r_pack_hs_1P;
reg     [15:0]r_hs_cnt;
reg     [8:0]r_frame_cnt;
reg     r_clk_cnt;
reg     [11:0]r_fast_x;
reg     [11:0]r_fast_y;
reg     r_fast_valid;
reg     r_fast_de;
reg     r_fast_hs;
reg     r_fast_vs;
reg     [47:0]r_fast_data;
reg     r_pack_de_1P;
reg     r_sync;

reg     [11:0]r_slow_x;
reg     [11:0]r_slow_y;
reg     r_slow_valid;
reg     r_slow_de;
reg     r_slow_hs;
reg     r_slow_vs;
reg     [47:0]r_slow_data;


//////Rx controller - Rx DHPY interface/////////////
wire [7:0] RxDataHS_0, RxDataHS_1, RxDataHS_2, RxDataHS_3, RxDataHS_4, RxDataHS_5, RxDataHS_6, RxDataHS_7;
wire [NUM_DATA_LANE-1:0][7:0] RxDataHS;
wire [NUM_DATA_LANE-1:0] RxValidHS, RxSyncHS;
wire [NUM_DATA_LANE-1:0] RxActiveHS;
wire RxUlpsClkNot, RxUlpsActiveClkNot;
wire [NUM_DATA_LANE-1:0] RxErrEsc, RxErrControl, RxErrSotSyncHS;
wire [NUM_DATA_LANE-1:0] RxUlpsEsc, RxUlpsActiveNot, RxSkewCalHS, RxStopState; 
wire [NUM_DATA_LANE-1:0] RxLPDTEsc;
wire [NUM_DATA_LANE-1:0] RxValidEsc;
wire [7:0] RxDataEsc_0;
wire [7:0] RxDataEsc_1;
wire [7:0] RxDataEsc_2;
wire [7:0] RxDataEsc_3;
wire [7:0] RxDataEsc_4;
wire [7:0] RxDataEsc_5;
wire [7:0] RxDataEsc_6;
wire [7:0] RxDataEsc_7;
wire TxRequestEsc, TxUlpsEsc, TxUlpsExit, TxLpdtEsc;
wire [3:0] TxTriggerEsc;      
wire [7:0] TxDataEsc;        
wire TxValidEsc, TxReadyEsc,  TxStopState,  TxUlpsActiveNot;
wire Direction, TurnRequest, TurnRequest_done, turnaround_timeout;

wire mipi_rx_reset_byte_HS_n;
assign  mipi_rx_data0_RST = ~i_arstn;
assign  mipi_rx_data1_RST = ~i_arstn;
assign  mipi_rx_data2_RST = ~i_arstn;
assign  mipi_rx_data3_RST = ~i_arstn;

generate
if (NUM_DATA_LANE == 1) begin
assign RxDataHS[0] = RxDataHS_0;
end             
else if (NUM_DATA_LANE == 2) begin
assign RxDataHS[0] = RxDataHS_0;
assign RxDataHS[1] = RxDataHS_1;
end
else if (NUM_DATA_LANE == 4) begin
assign RxDataHS[0] = RxDataHS_0;
assign RxDataHS[1] = RxDataHS_1;
assign RxDataHS[2] = RxDataHS_2;
assign RxDataHS[3] = RxDataHS_3;
end
endgenerate


////////////////////////////////////////////////////////////////
/// glue logic for color bar display example design
wire        w_pll_locked;
wire        w_global_rstn;
wire        w_lcd_rstn;
wire        w_pixel_rstn;
wire [8:0]  w_frame_cnt;
wire        esc_clk = 1'b0; // used by 2p5g

wire        w_fb_clk_arstn;
wire        w_fb_clk_arst;
wire        w_dphy_byte_clk_arstn;
wire        w_dphy_byte_clk_arst;
wire        w_rx_byte_clk_arstn;
wire        w_rx_byte_clk_arst;

wire        w_vsync;
wire        w_hsync;
wire        w_valid;
wire [9:0]  w_out_x;
wire [9:0]  w_out_y;

assign o_lcd_rstn  = w_lcd_rstn;
assign w_pll_locked  = i_pll_locked & i_mipi_tx_pll_locked;
assign led[3]     = w_frame_cnt[5];

reset_ctrl #(
    .NUM_RST       (6),
    .CYCLE         (4),
    .IN_RST_ACTIVE (6'b0000),
    .OUT_RST_ACTIVE(6'b1010)
) inst_reset_ctrl (
    .i_arst({6{w_global_rstn}}),
    .i_clk({
        {2{i_fb_clk}}, {2{mipi_rx_clk_CLKOUT}}, {2{i_mipi_tx_pclk}}
    }),
    .o_srst({
        w_fb_clk_arst,
        w_fb_clk_arstn,
        w_rx_byte_clk_arst,
        w_rx_byte_clk_arstn,
        w_dphy_byte_clk_arst,
        w_dphy_byte_clk_arstn
    })
);


dsichk #(
.MAX_HRES (MAX_HRES),
.MAX_VRES (MAX_VRES),
.HSP      (HSP     ),
.HBP      (HBP     ),
.HFP      (HFP     ),
.VSP      (VSP     ),
.VBP      (VBP     ),
.VFP      (VFP     )
) dsichk_inst (
    .i_arstn        (i_arstn        ),
    .pll_locked     (w_pll_locked   ),
    .o_pixel_rstn   (w_pixel_rstn   ),
    .o_global_rstn  (w_global_rstn  ),
    
    .i_fb_clk       (i_fb_clk       ),
    .i_sysclk       (i_sysclk       ),
    
    .o_vsync        (w_vsync        ),
    .o_hsync        (w_hsync        ),
    .o_valid        (w_valid        ),
    .o_out_x        (w_out_x        ),
    .o_out_y        (w_out_y        ),

    .i_inject_err1  (1'b1   ),
    .i_inject_err2  (1'b1           ),
    .o_hsync_match  (led[0]      ),
    .o_vsync_match  (led[1]      ),
    .o_pdata_match  (led[2]      ),
    .o_frame_cnt    (w_frame_cnt    ),
    
    .i_vsync        (vsync          ),
    .i_hsync        (hsync          ),                 
    .i_valid        (pixel_data_valid),                 
    .i_pdata        (pixel_data     ), 

    .i_clr_cnt      (1'b0           ),
    
    .i_axi_awready  (w_axi_awready  ),
    .i_axi_wready   (w_axi_wready   ),
    .i_axi_bvalid   (w_axi_bvalid   ),
    .o_axi_awaddr   (w_axi_awaddr   ),
    .o_axi_awvalid  (w_axi_awvalid  ),
    .o_axi_wdata    (w_axi_wdata    ),
    .o_axi_wvalid   (w_axi_wvalid   ),
    .o_axi_bready   (w_axi_bready   ),
    
    .i_axi_arready  (w_axi_arready  ),
    .i_axi_rdata    (w_axi_rdata    ),
    .i_axi_rvalid   (w_axi_rvalid   ),
    .o_axi_araddr   (w_axi_araddr   ),
    .o_axi_arvalid  (w_axi_arvalid  ),
    .o_axi_rready   (w_axi_rready   )
);

//////////// MIPI DSI TX 1st Channel ///////////////////
efx_dsi_tx
// #(
//     // note: not all parameters are pull out.. 
//     .tLPX_NS                 (tLPX_NS               ),
//     .tINIT_NS                (tINIT_NS              ),
//     .tLP_EXIT_NS             (tLP_EXIT_NS           ),
//     .BTA_TIMEOUT_NS          (BTA_TIMEOUT_NS        ),
//     .tD_TERM_EN_NS           (tD_TERM_EN_NS         ),
//     .tHS_PREPARE_ZERO_NS     (tHS_PREPARE_ZERO_NS   ),
//     .tHS_PREPARE_NS          (tHS_PREPARE_NS        ),
//     .tWAKEUP_NS              (tWAKEUP_NS            ),
//     .tHS_EXIT_NS             (tHS_EXIT_NS           ),
//     .tHS_ZERO_NS             (tHS_ZERO_NS           ),
//     .tHS_TRAIL_NS            (tHS_TRAIL_NS          ),
//     .NUM_DATA_LANE           (NUM_DATA_LANE         ),
//     .HS_BYTECLK_MHZ          (HS_BYTECLK_MHZ        ),
//     .CLOCK_FREQ_MHZ          (CLOCK_FREQ_MHZ        ),
//     .DPHY_CLOCK_MODE         (DPHY_CLOCK_MODE       ),
//     .PACK_TYPE               (PACK_TYPE             ),
//     .PACKET_SEQUENCES        (PACKET_SEQUENCES      ),
//     .MAX_HRES                ({5'h0,MAX_HRES}              ),
//     .ENABLE_BIDIR            (ENABLE_BIDIR          )
// )
inst_efx_dsi_tx1
(
    .reset_n            (w_global_rstn          ),
    .clk                (i_mipi_clk             ),  // 100
    .reset_byte_HS_n    (w_dphy_byte_clk_arstn  ),
    .clk_byte_HS        (i_mipi_tx_pclk         ),  // 1000/8=125
    .reset_pixel_n      (w_pixel_rstn           ),
    .clk_pixel          (i_sysclk               ),
    .Tx_LP_CLK_P        (mipi_dp_clk_LP_P_OUT),
    .Tx_LP_CLK_P_OE     (mipi_dp_clk_LP_P_OE),
    .Tx_LP_CLK_N        (mipi_dp_clk_LP_N_OUT),
    .Tx_LP_CLK_N_OE     (mipi_dp_clk_LP_N_OE),
    .Tx_HS_C            (mipi_dp_clk_HS_OUT),
    .Tx_HS_enable_C     (mipi_dp_clk_HS_OE),
    
    // ----- DLane -----------
    // LVDS data lane
    .Tx_LP_D_P          ({mipi_dp_data3_LP_P_OUT, mipi_dp_data2_LP_P_OUT, mipi_dp_data1_LP_P_OUT, mipi_dp_data0_LP_P_OUT}),
    .Tx_LP_D_P_OE       ({mipi_dp_data3_LP_P_OE, mipi_dp_data2_LP_P_OE, mipi_dp_data1_LP_P_OE, mipi_dp_data0_LP_P_OE}),
    .Tx_LP_D_N          ({mipi_dp_data3_LP_N_OUT, mipi_dp_data2_LP_N_OUT, mipi_dp_data1_LP_N_OUT, mipi_dp_data0_LP_N_OUT}),
    .Tx_LP_D_N_OE       ({mipi_dp_data3_LP_N_OE, mipi_dp_data2_LP_N_OE, mipi_dp_data1_LP_N_OE, mipi_dp_data0_LP_N_OE}),
    .Tx_HS_D_0          (mipi_dp_data0_HS_OUT),
    .Tx_HS_D_1          (mipi_dp_data1_HS_OUT),
    .Tx_HS_D_2          (mipi_dp_data2_HS_OUT),
    .Tx_HS_D_3          (mipi_dp_data3_HS_OUT),
    // control signal to LVDS IO
    .Tx_HS_enable_D     ({mipi_dp_data3_HS_OE, mipi_dp_data2_HS_OE, mipi_dp_data1_HS_OE, mipi_dp_data0_HS_OE}),
    .Rx_LP_D_P          (mipi_dp_data0_LP_P_IN),
    .Rx_LP_D_N          (mipi_dp_data0_LP_N_IN),
    
    //AXI4-Lite Interface
    .axi_clk        (i_fb_clk       ), 
    .axi_reset_n    (w_global_rstn  ),
    .axi_awaddr     (w_axi_awaddr   ),//Write Address. byte address.
    .axi_awvalid    (w_axi_awvalid  ),//Write address valid.
    .axi_awready    (w_axi_awready  ),//Write address ready.
    .axi_wdata      (w_axi_wdata    ),//Write data bus.
    .axi_wvalid     (w_axi_wvalid   ),//Write valid.
    .axi_wready     (w_axi_wready   ),//Write ready.
                          
    .axi_bvalid     (w_axi_bvalid   ),//Write response valid.
    .axi_bready     (w_axi_bready   ),//Response ready.      
    .axi_araddr     (w_axi_araddr   ),//Read address. byte address.
    .axi_arvalid    (w_axi_arvalid  ),//Read address valid.
    .axi_arready    (w_axi_arready  ),//Read address ready.
    .axi_rdata      (w_axi_rdata    ),//Read data.
    .axi_rvalid     (w_axi_rvalid   ),//Read valid.
    .axi_rready     (w_axi_rready   ),//Read ready.

    .hsync            (~w_hsync     ),
    .vsync            (~w_vsync     ),
    .vc               (2'b0         ),
    .datatype         (6'h3E        ),
    .pixel_data       ({4'b0, {3{w_out_y,w_out_x}}}),
    .pixel_data_valid (w_valid      ),
    .haddr            ({5'h0, MAX_HRES}     ),
    .TurnRequest_dbg  (1'b0         ),
    .TurnRequest_done (             ),
    .irq              (             )
);

/////////MIPI DSI RX ///////////////
mipi_dsi_rx 
// #(
//     .tLPX_NS                (tLPX_NS                ),
//     .tCLK_TERM_EN_NS        (tCLK_TERM_EN_NS        ),
//     .tD_TERM_EN_NS          (tD_TERM_EN_NS          ),
//     .tHS_SETTLE_NS          (tHS_SETTLE_NS          ),
//     .tHS_PREPARE_ZERO_NS    (tHS_PREPARE_ZERO_NS    ),
//     .HS_BYTECLK_MHZ         (HS_BYTECLK_MHZ         ),
//     .CLOCK_FREQ_MHZ         (CLOCK_FREQ_MHZ         ),
//     .NUM_DATA_LANE          (NUM_DATA_LANE          ),
//     .ENABLE_USER_DESKEWCAL  (ENABLE_USER_DESKEWCAL  ),
//     .DPHY_CLOCK_MODE        (DPHY_CLOCK_MODE        ),
//     .ENABLE_BIDIR           (ENABLE_BIDIR           ),
//     .tLP_EXIT_NS            (tLP_EXIT_NS            ),
//     .BTA_TIMEOUT_NS         (BTA_TIMEOUT_NS         ),
//     .tHS_PREPARE_NS         (tHS_PREPARE_NS         ),
//     .tWAKEUP_NS             (tWAKEUP_NS             ),
//     .tHS_EXIT_NS            (tHS_EXIT_NS            ),
//     .tHS_ZERO_NS            (tHS_ZERO_NS            ),
//     .tHS_TRAIL_NS           (tHS_TRAIL_NS           ),
//     .tINIT_NS               (tINIT_NS               ),
//     .PACK_TYPE              (4'b1111                ),
// //    .AREGISTER              (AREGISTER              ),
//     .PACKET_SEQUENCES       (PACKET_SEQUENCES       ),
//     .PIXEL_FIFO_DEPTH       (PIXEL_FIFO_DEPTH       ),
//     .HS_CMD_FIFO_DEPTH      (HS_CMD_FIFO_DEPTH      ),
//     .LP_CMD_FIFO_DEPTH      (LP_CMD_FIFO_DEPTH      ),
//     .LP_CMD_RDATAFIFO_DEPTH (LP_CMD_RDATAFIFO_DEPTH )
efx_dsi_rx_inst (
    .reset_n          (w_global_rstn            ),
    .clk              (i_mipi_clk               ),   
    .reset_byte_HS_n  (w_rx_byte_clk_arstn      ),   
    .clk_byte_HS      (mipi_rx_clk_CLKOUT       ),
    .reset_pixel_n    (w_pixel_rstn             ),
    .clk_pixel        (i_sysclk                 ),
    .Rx_LP_CLK_P      (mipi_rx_clk_LP_P_IN      ), 
    .Rx_LP_CLK_N      (mipi_rx_clk_LP_N_IN      ),
    .Rx_HS_enable_C   (mipi_rx_clk_HS_ENA       ),
    .LVDS_termen_C    (mipi_rx_clk_HS_TERM      ),
    .Rx_LP_D_P        ({mipi_rx_data3_LP_P_IN,mipi_rx_data2_LP_P_IN,mipi_rx_data1_LP_P_IN,mipi_rx_data0_LP_P_IN}),
    .Rx_LP_D_N        ({mipi_rx_data3_LP_N_IN,mipi_rx_data2_LP_N_IN,mipi_rx_data1_LP_N_IN,mipi_rx_data0_LP_N_IN}),
    .Rx_HS_D_0        (mipi_rx_data0_HS_IN      ),
    .Rx_HS_D_1        (mipi_rx_data1_HS_IN      ),
    .Rx_HS_D_2        (mipi_rx_data2_HS_IN      ),
    .Rx_HS_D_3        (mipi_rx_data3_HS_IN      ),
    .Rx_HS_enable_D   ({mipi_rx_data3_HS_ENA,mipi_rx_data2_HS_ENA,mipi_rx_data1_HS_ENA,mipi_rx_data0_HS_ENA}                ),
    .LVDS_termen_D    ({mipi_rx_data3_HS_TERM,mipi_rx_data2_HS_TERM,mipi_rx_data1_HS_TERM,mipi_rx_data0_HS_TERM}            ),
    .fifo_rd_enable   ({mipi_rx_data3_FIFO_RD,mipi_rx_data2_FIFO_RD,mipi_rx_data1_FIFO_RD,mipi_rx_data0_FIFO_RD}            ),
    .fifo_rd_empty    ({mipi_rx_data3_FIFO_EMPTY,mipi_rx_data2_FIFO_EMPTY,mipi_rx_data1_FIFO_EMPTY,mipi_rx_data0_FIFO_EMPTY}),
    .DLY_enable_D     (                         ),
    .DLY_inc_D        (                         ),
    .u_dly_enable_D   (4'h0                     ),
    .u_dly_inc_D      (4'h0                     ),  
    .Tx_LP_D_P        (mipi_rx_data0_LP_P_OUT   ),
    .Tx_LP_D_P_OE     (mipi_rx_data0_LP_P_OE    ),
    .Tx_LP_D_N        (mipi_rx_data0_LP_N_OUT   ),
    .Tx_LP_D_N_OE     (mipi_rx_data0_LP_N_OE    ),
    .axi_clk          (i_fb_clk                 ),      
    .axi_reset_n      (w_global_rstn            ),      
    .axi_awaddr       (                         ),      
    .axi_awvalid      (                         ),      
    .axi_awready      (                         ),      
    .axi_wdata        (                         ),      
    .axi_wvalid       (                         ),      
    .axi_wready       (                         ),      
    .axi_bvalid       (                         ),      
    .axi_bready       (                         ),      
    .axi_araddr       (                         ),      
    .axi_arvalid      (                         ),      
    .axi_arready      (                         ),      
    .axi_rdata        (                         ),      
    .axi_rvalid       (                         ),      
    .axi_rready       (                         ),      
    .hsync            (hsync                    ),    
    .vsync            (vsync                    ),
    .vc               (vc                       ),
    .word_count       (word_count               ),
    .pixel_data       (pixel_data               ), 
    .pixel_data_valid (pixel_data_valid         ),
    .pixel_vc         (                         ),
    .pixel_format     (                         ),
    .datatype         (datatype                 ),
    .video_format     (6'h3E                    ),
    .irq              (                         )
);


endmodule
