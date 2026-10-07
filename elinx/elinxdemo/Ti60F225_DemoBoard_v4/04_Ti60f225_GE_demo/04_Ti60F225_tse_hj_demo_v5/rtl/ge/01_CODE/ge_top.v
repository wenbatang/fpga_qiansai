/*******************************************************************\
# Copyright    : Copyright (C), 2008 - 2020
#                XL  Technologics Co.,  Ltd.
# File name    : fpga_top.v
# Version      : 1.0
# Date         : 2020-09-24
# Description  :
#
# Other        :
# Proc List    :
# Date         : 2011-05-12
# Author       : Ramsey Wang
# Modification : Create file
# History      :
#-----------------------------------------------------
#    Author        Date        Version       Description
#     lw         2020-09-24      1.0          initial
#
\*******************************************************************/

`timescale 1ns / 1ps

module ge_top #
    (
    parameter    C_SIM               = 1'b0
    )
    (
     input 											clk_25m,
  	 input 											clk_10m,
     input 											rxc,
     input                      clk_125m,
     input                      Sys_pll_locked,  
	 	 input												pll_rxc,   
     input  [3:0]               rxd_hi_i,
     input  [3:0]               rxd_lo_i,
     input 											rx_dv_HI,
 		 input 											rx_dv_LO,

     output 		reg								tx_en_o_HI,
  	 output 		reg								tx_en_o_LO,
     
     output                     txc_hi_o,
     output                     txc_lo_o,
     output reg [3:0]           txd_hi_o,
     output reg [3:0]           txd_lo_o,

     output 											mdc_o_HI,
     output 											mdc_o_LO,
     output                     rst_n,
     output                     mdio_o,
     output                     mdio_oe,     
     input                      mdio_i,     
     output 										phy_rst_n
    );

//*******************************************************************\
//    parameter
//*******************************************************************/
localparam   U_DLY                  = 1;
localparam   CNT_10MS 							= 250000;

//*******************************************************************\
//   signal
//*******************************************************************/
//CLK && RESET
wire          rst_sys_n;

wire 					timer_pulse;
wire 	[7:0]		tx_data;
wire  [7:0]   gm_tx_d;
wire          gm_tx_en;
reg   [4:0]   posedge_data_temp ;
reg   [4:0]   negedge_data_temp ;   
reg 	[27:0]  cnt_10ms = 'd0;
//*******************************************************************
//   main code
//*******************************************************************

assign phy_rst_n = (cnt_10ms ==  CNT_10MS - 1);

always @( posedge clk_25m )
begin
		if( cnt_10ms ==  CNT_10MS - 1 )
				cnt_10ms <= cnt_10ms ;
		else
				cnt_10ms <= cnt_10ms + 1'b1;
end 

assign rst_sys_n = Sys_pll_locked;  //pllΪ��ʱ������Ϊ��ʱʧ��


//*******************************************************************//
//txc process
//*******************************************************************//


assign txc_hi_o = 1'b1;
assign txc_lo_o = 1'b0;






	timer #(
			.SIM_FLAG(0)
		) inst_timer (
			.tx_clk      (clk_125m),
			.rst         (1'b0),//(!logic_rstn),
			.timer_pulse (timer_pulse)
		);

	gen_frame_ctrl inst_gen_frame_ctrl (
		.tx_clk      (clk_125m),
		.rst         (1'b0),
		.timer_pulse (timer_pulse),
		.tx_en       (gm_tx_en),
		.tx_data     (gm_tx_d)
	);

    always @( posedge clk_125m )
    begin
            txd_lo_o <= gm_tx_d[7:4];
            tx_en_o_LO <= gm_tx_en;
    end
     always @( posedge clk_125m )
    begin
             txd_hi_o<= gm_tx_d[3:0];
            tx_en_o_HI <= gm_tx_en;
    end




// always @(posedge clk_125m)
// begin
   
//     rgmii_tx_ctl_HI <=gm_tx_en;
//     rgmii_tx_ctl_LO <= gm_tx_en;// ^ tx_er;
//     rgmii_txd_HI <= gm_tx_d[3:0];
//     rgmii_txd_LO <= gm_tx_d[7:4];
// end

/********************************************************
*
*********************************************************/    

assign mdc_o_HI = 1'b0;
assign mdc_o_LO = 1'b1;

	phy_ctrl_top u_top(

  /*i*/.RST_N			(rst_sys_n),
  /*i*/.clk_25m			(clk_10m),
//  /*o*/.ETH_MDC			(mdc_o),
  /*o*/.ETH_MDIO_OUT(mdio_o),
  /*i*/.ETH_MDIO_IN	(mdio_i),
  /*o*/.ETH_MDIO_OE (mdio_oe)
  
  );
  
  mr_rate_detect 
#(
    .CYC_MEASURE_CLK_IN_10_MSEC (24'h03D090) // 100MHz clock has 0x0F4240 samples in ten milliseconds 
)u_mr_rate_detec 
(
    /*i*/.refclock					(pll_rxc),         // clock to be measured
    /*i*/.measure_clk				(clk_25m),      // fixed reference clock to this module, eg. 100MHz
    /*i*/.reset							(1'b0),            // reset signal 
    /*i*/.enable						(1'b1),	 
    /*o*/.refclock_measure	(),
    /*o*/.valid             ()
);

  mr_rate_detect 
#(
    .CYC_MEASURE_CLK_IN_10_MSEC (24'h03D090) // 100MHz clock has 0x0F4240 samples in ten milliseconds 
)u_mr_rate_detec1 
(
    /*i*/.refclock					(clk_125m),         // clock to be measured
    /*i*/.measure_clk				(clk_25m),      // fixed reference clock to this module, eg. 100MHz
    /*i*/.reset							(1'b0),            // reset signal 
    /*i*/.enable						(1'b1),	 
    /*o*/.refclock_measure	(),
    /*o*/.valid             ()
);


endmodule