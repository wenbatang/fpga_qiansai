module ti60_camera_ppi_top #(parameter integer PROC_WIDTH=640,PROC_HEIGHT=480,UART_BAUD=2000000,UART_PAYLOAD_BYTES=16384)
(input wire CLK_25M,CLK_27M,core_clk,hdmi_tx_slow_clk,
 input wire sdram_clk,rx_cal_clk,tx_cal_clk,tx_cal_clk_90edge,pll_locked,user_pll_locked,core_pll_locked,
 input wire [3:0] style_keys_n,input wire uart_rx,output wire uart_tx,
 input wire io_cam_sda_IN,io_cam_scl_IN,
 output wire io_cam_sda_OUT,io_cam_sda_OE,io_cam_scl_OUT,io_cam_scl_OE,o_cam_rst_p,
 input wire i_cam_ck_LP_P_IN,i_cam_ck_LP_N_IN,i_cam_ck_CLKOUT,
 output wire o_cam_ck_HS_TERM,o_cam_ck_HS_ENA,
 input wire[7:0] cam_d0_HS_IN,
 input wire cam_d0_LP_P_IN,cam_d0_LP_N_IN,cam_d0_FIFO_EMPTY,
 output wire cam_d0_HS_TERM,cam_d0_HS_ENA,cam_d0_RST,cam_d0_FIFO_RD,
 input wire[7:0] cam_d1_HS_IN,
 input wire cam_d1_LP_P_IN,cam_d1_LP_N_IN,cam_d1_FIFO_EMPTY,
 output wire cam_d1_HS_TERM,cam_d1_HS_ENA,cam_d1_RST,cam_d1_FIFO_RD,
 input wire[7:0] cam_d2_HS_IN,
 input wire cam_d2_LP_P_IN,cam_d2_LP_N_IN,cam_d2_FIFO_EMPTY,
 output wire cam_d2_HS_TERM,cam_d2_HS_ENA,cam_d2_RST,cam_d2_FIFO_RD,
 input wire[7:0] cam_d3_HS_IN,
 input wire cam_d3_LP_P_IN,cam_d3_LP_N_IN,cam_d3_FIFO_EMPTY,
 output wire cam_d3_HS_TERM,cam_d3_HS_ENA,cam_d3_RST,cam_d3_FIFO_RD,
 output wire DDR3_PLL_RSTN,USER_PLL_RSTN,CORE_PLL_RSTN,
 output wire [9:0] tmds_tx_clk_TX_DATA,tmds_tx_data0_TX_DATA,tmds_tx_data1_TX_DATA,tmds_tx_data2_TX_DATA,
 output wire tmds_tx_clk_TX_RST,tmds_tx_data0_TX_RST,tmds_tx_data1_TX_RST,tmds_tx_data2_TX_RST,
 output wire tmds_tx_clk_TX_OE,tmds_tx_data0_TX_OE,tmds_tx_data1_TX_OE,tmds_tx_data2_TX_OE,
 output          [2:0]           pll_shift,  
output          [4:0]           pll_shift_sel,
output                          pll_shift_ena,  


output                          ddr_ck_hi,
output                          ddr_ck_lo,
output                          ddr_reset_n,
output          [1-1:0] ddr_cke,     
output          [14-1:0] ddr_addr,
output          [3-1:0]ddr_ba,
output                          ddr_cas_n,
output          [1-1:0] 
                                ddr_cs_n,
output                          ddr_ras_n,
output                          ddr_we_n,

input           [2-1:0] ddr_dqs_in_hi,
input           [2-1:0] ddr_dqs_in_lo,
input           [16-1:0]  ddr_dq_in_hi,
input           [16-1:0]  ddr_dq_in_lo,

output          [2-1:0] ddr_dqs_oe,
output          [2-1:0] ddr_dqs_oe_n,
output          [16-1:0]  ddr_dq_oe,    
output          [2-1:0] ddr_dqs_out_hi,
output          [2-1:0] ddr_dqs_out_lo,
output          [16-1:0]  ddr_dq_out_hi,
output          [16-1:0]  ddr_dq_out_lo,
output          [2-1:0]  ddr_dm_hi,
output          [2-1:0]  ddr_dm_lo,
output          [1-1:0] ddr_odt);
 wire ui_clk=core_clk,pixel_clk=hdmi_tx_slow_clk;
 wire sys_rst_n,ddr_reset,reset_ui,reset_pixel,calibrated,soc_reset,reset_byte;
 board_boot boot(.clk(CLK_25M),.keys_n(style_keys_n),.reset_n(sys_rst_n));
 assign DDR3_PLL_RSTN=sys_rst_n;assign USER_PLL_RSTN=sys_rst_n;assign CORE_PLL_RSTN=sys_rst_n;
 reset_sync ddr_rst(.clk(ui_clk),.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked),.reset(ddr_reset));
 reset_sync rst_ui(.clk(ui_clk),.async_reset(ddr_reset || !calibrated),.reset(reset_ui));
 reset_sync rst_pixel(.clk(pixel_clk),.async_reset(!sys_rst_n || !pll_locked || !core_pll_locked || !user_pll_locked || !calibrated),.reset(reset_pixel));
 reset_sync rst_byte(.clk(i_cam_ck_CLKOUT),.async_reset(reset_ui),.reset(reset_byte));
 assign cam_d0_RST=reset_byte;assign cam_d1_RST=reset_byte;assign cam_d2_RST=reset_byte;assign cam_d3_RST=reset_byte;
 wire cam_vs,cam_hs,cam_valid;
 wire[63:0] cam_pixels;wire[31:0] ppi_data;
 wire[3:0] ppi_valid,ppi_sync,ppi_sot_error,dphy_control_error,dphy_escape_error;
 wire bridge_error,bridge_transport_fault;
 assign uart_tx=1'b1;
camera_dphy inst_camera_dphy
		(
              .reset_n			(!reset_ui),
              .clk				(core_clk),
              .reset_byte_HS_n(!reset_byte),
              .clk_byte_HS		  (i_cam_ck_CLKOUT),
              
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
              .Rx_HS_D_4(8'd0),
              .Rx_HS_D_5(8'd0),
              .Rx_HS_D_6(8'd0),
              .Rx_HS_D_7(8'd0),
              .Rx_HS_enable_D		({cam_d3_HS_ENA    ,cam_d2_HS_ENA    ,cam_d1_HS_ENA    ,cam_d0_HS_ENA    }),//( w_cam_d_HS_ENA),
              .LVDS_termen_D		({cam_d3_HS_TERM   ,cam_d2_HS_TERM   ,cam_d1_HS_TERM   ,cam_d0_HS_TERM   }),
              .fifo_rd_enable		({cam_d3_FIFO_RD   ,cam_d2_FIFO_RD   ,cam_d1_FIFO_RD   ,cam_d0_FIFO_RD   }),
              .fifo_rd_empty		({cam_d3_FIFO_EMPTY,cam_d2_FIFO_EMPTY,cam_d1_FIFO_EMPTY,cam_d0_FIFO_EMPTY}),
              .DLY_enable_D		       (),
              .DLY_inc_D			(),
              .u_dly_enable_D(4'd0),
              .u_dly_inc_D(4'd0),
              

 .RxDataHS_0(ppi_data[7:0]),.RxDataHS_1(ppi_data[15:8]),.RxDataHS_2(ppi_data[23:16]),.RxDataHS_3(ppi_data[31:24]),
 .RxDataHS_4(),.RxDataHS_5(),.RxDataHS_6(),.RxDataHS_7(),.RxValidHS(ppi_valid),.RxSyncHS(ppi_sync),
 .RxErrSotSyncHS(ppi_sot_error),.RxErrControl(dphy_control_error),.RxErrEsc(dphy_escape_error),
 .RxActiveHS(),.RxStopState(),.RxUlpsEsc(),.RxUlpsActiveNot(),.RxLPDTEsc(),.RxValidEsc(),
 .RxDataEsc_0(),.RxDataEsc_1(),.RxDataEsc_2(),.RxDataEsc_3(),.RxDataEsc_4(),.RxDataEsc_5(),.RxDataEsc_6(),.RxDataEsc_7(),
 .RxSkewCalHS(),.RxUlpsClkNot(),.RxUlpsActiveClkNot());
 assign cam_pixels[63:40]=24'd0;
 csi_ppi_bridge bridge(.byte_clk(i_cam_ck_CLKOUT),.byte_reset(reset_byte),.ui_clk(core_clk),.ui_reset(reset_ui),
  .ppi_data(ppi_data),.ppi_valid(ppi_valid),.ppi_sync(ppi_sync),.ppi_sot_error(ppi_sot_error),
  .control_error(|dphy_control_error || |dphy_escape_error),
  .vs(cam_vs),.hs(cam_hs),.valid(cam_valid),.raw(cam_pixels[39:0]),.packet_error(bridge_error),
  .transport_fault(bridge_transport_fault),.good_lines(),.error_packets());
 wire[15:0] paddr;wire psel,penable,pwrite,pready,pslverror,irq;
 wire[31:0] pwdata,prdata;wire scl_release,sda_release,sensor_reset_n;
 // V7 active-high module reset, not the bare sensor's XSHUTDN polarity.
 assign o_cam_rst_p=reset_ui || !sensor_reset_n;
 assign io_cam_scl_OUT=1'b0;assign io_cam_sda_OUT=1'b0;
 assign io_cam_scl_OE=!reset_ui && !scl_release;assign io_cam_sda_OE=!reset_ui && !sda_release;
 control_soc cpu(.io_systemClk(ui_clk),.io_asyncReset(reset_ui),.io_systemReset(soc_reset),
  .jtagCtrl_enable(1'b0),.jtagCtrl_tdi(1'b0),.jtagCtrl_capture(1'b0),.jtagCtrl_shift(1'b0),
  .jtagCtrl_update(1'b0),.jtagCtrl_reset(1'b1),.jtagCtrl_tdo(),.jtagCtrl_tck(1'b0),
  .userInterruptA(irq),.io_apbSlave_0_PADDR(paddr),.io_apbSlave_0_PENABLE(penable),
  .io_apbSlave_0_PRDATA(prdata),.io_apbSlave_0_PREADY(pready),.io_apbSlave_0_PSEL(psel),
  .io_apbSlave_0_PSLVERROR(pslverror),.io_apbSlave_0_PWDATA(pwdata),.io_apbSlave_0_PWRITE(pwrite));
 wire[29:0] awaddr,araddr;wire awvalid,awready,wvalid,wready,bvalid,bready,arvalid,arready,rvalid,rlast,rready;
 wire[127:0] wdata,rdata;wire[1:0] bresp,rresp;
 wire[23:0] rgb;wire hsync,vsync,de;
 video_system #(.WIDTH(PROC_WIDTH),.HEIGHT(PROC_HEIGHT)) system(.clk(ui_clk),.reset(reset_ui || soc_reset),
  .pixel_clk(pixel_clk),.pixel_reset(reset_pixel),.calibrated(calibrated),
  .paddr(paddr),.psel(psel),.penable(penable),.pwrite(pwrite),.pwdata(pwdata),.prdata(prdata),.pready(pready),.pslverror(pslverror),.irq(irq),
  .keys_n(style_keys_n),.scl_in(io_cam_scl_IN),.sda_in(io_cam_sda_IN),.scl_release(scl_release),.sda_release(sda_release),.sensor_reset_n(sensor_reset_n),
  .cam_vs(cam_vs),.cam_hs(cam_hs),.cam_valid(cam_valid),.cam_raw(cam_pixels[39:0]),
  .cam_error(bridge_error),
  .awaddr(awaddr),.awvalid(awvalid),.awready(awready),.wdata(wdata),.wvalid(wvalid),.wready(wready),.bresp(bresp),.bvalid(bvalid),.bready(bready),
  .araddr(araddr),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rresp(rresp),.rvalid(rvalid),.rlast(rlast),.rready(rready),
  .display_rgb(rgb),.hsync(hsync),.vsync(vsync),.de(de));
tmds_efx display(.clk(pixel_clk),.reset(reset_pixel),.rgb(rgb),.de(de),.hsync(hsync),.vsync(vsync),
 .blue(tmds_tx_data0_TX_DATA),.green(tmds_tx_data1_TX_DATA),.red(tmds_tx_data2_TX_DATA),.clock_word(tmds_tx_clk_TX_DATA));
assign tmds_tx_clk_TX_RST=reset_pixel;assign tmds_tx_data0_TX_RST=reset_pixel;
assign tmds_tx_data1_TX_RST=reset_pixel;assign tmds_tx_data2_TX_RST=reset_pixel;
assign tmds_tx_clk_TX_OE=1'b1;assign tmds_tx_data0_TX_OE=1'b1;
assign tmds_tx_data1_TX_OE=1'b1;assign tmds_tx_data2_TX_OE=1'b1;
ddr3_top                 u_ddr3_top
(

.axi_clk                (ui_clk            ),
.core_clk               (ui_clk            ),
.sdram_clk              (sdram_clk           ),  
.rx_cal_clk             (rx_cal_clk          ),
.tx_cal_clk             (tx_cal_clk          ),
.tx_cal_clk_90edge      (tx_cal_clk_90edge   ),
.rstn                   (!ddr_reset             ),      
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
.app_sr_active                  (),
.app_ref_ack                    (),
.app_zq_ack                     (),

// Slave Interface Write Address Ports
 .s_axi_awid(4'd0),.s_axi_awaddr({2'b0,awaddr}),.s_axi_awlen(8'd0),.s_axi_awsize(3'd4),.s_axi_awburst(2'd1),
 .s_axi_awlock(1'b0),.s_axi_awcache(4'b0011),.s_axi_awprot(3'd0),.s_axi_awqos(4'd0),.s_axi_awvalid(awvalid),.s_axi_awready(awready),
 .s_axi_wdata(wdata),.s_axi_wstrb(16'hffff),.s_axi_wlast(1'b1),.s_axi_wvalid(wvalid),.s_axi_wready(wready),
 .s_axi_bid(),.s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),
 .s_axi_arid(4'd0),.s_axi_araddr({2'b0,araddr}),.s_axi_arlen(8'd15),.s_axi_arsize(3'd4),.s_axi_arburst(2'd1),
 .s_axi_arlock(1'b0),.s_axi_arcache(4'b0011),.s_axi_arprot(3'd0),.s_axi_arqos(4'd0),.s_axi_arvalid(arvalid),.s_axi_arready(arready),
 .s_axi_rid(),.s_axi_rdata(rdata),.s_axi_rresp(rresp),.s_axi_rlast(rlast),.s_axi_rvalid(rvalid),.s_axi_rready(rready),
 .cal_done(calibrated));
endmodule
