/*-----------------------------------------------------------------------

CONFIDENTIAL IN CONFIDENCE
This confidential and proprietary software may be only used as authorized
by a licensing agreement from  EdgeWang (Thereturnofbingo).
In the event of publication, the following notice is applicable:
Copyright (C) 2023-20xx  EdgeWang Corporation
The entire notice above must be reproduced on all authorized copies.
Author				:		EdgeWang
Technology blogs 	: 	
Email Address 		: 		
Filename			:		top
Date				:		2023-06-06
Description			:		
Modification History	:
Date			By			Version			Change Description
=========================================================================
23/6/6		EdgeWang	1.0				Original

****************************************************************/

`timescale 1ns/1ns
module top
(
	//led interface
  input [1:0] key_i,
  input sys_pll_LOCKED,
  input gpio_clk_27m,
  input rxd,
  output txd,
  output [3:0] led,
  output sys_pll_RSTN
	);
  //============================================================
  // signal
  //============================================================
  wire       led_data1;
  wire       led_data2;
  wire       led_data3;
  wire       sys_rst_n;
  wire       key_sw_en1;
  wire       key_sw_en2;
  wire       key_sw_en3;
  //============================================================
  //
  //============================================================

assign sys_pll_RSTN = key_i[0];
assign sys_rst_n = sys_pll_LOCKED;
// wire led_clk;

//=============================================== 
//
//===============================================
wire RdEmpty;
wire tx_valid;
wire rx_valid;
wire [7:0] tx_data;
wire [7:0] rx_data;
wire [7:0] RdDNum;  
  DC_FIFO # (
    .FIFO_MODE("Normal"),
    .DATA_WIDTH(8),
    .FIFO_DEPTH(128)
  )
  DC_FIFO_inst (
    .Reset(1'b0),
    .WrClk(gpio_clk_27m),
    .WrEn(rx_valid),
    .WrDNum(),
    .WrFull(),
    .WrData(rx_data),
    .RdClk(gpio_clk_27m),
    .RdEn(tx_req & (~RdEmpty)),
    .RdDNum(RdDNum),
    .RdEmpty(RdEmpty),
    .DataVal(tx_valid),
    .RdData(tx_data)
  );

  uart_rx_tx # (
    .CLK_RATE(27000000),
    .BPS_RATE(115200),
    .STOP_BIT_W(1),
    .CHECKSUM_MODE(2'b00),
    .CHECKSUM_EN(1'b0)
  )
  uart_rx_tx_inst (
    .clk(gpio_clk_27m),
    .rst_n(1'b1),
    .rxd(rxd),
    .txd(txd),
    .tx_valid(tx_valid),
    .tx_data(tx_data),
    .tx_req(tx_req),
    .rx_valid(rx_valid),
    .rx_data(rx_data)
  );

  assign led[1:0] = {rxd,txd};
  assign led[3:2] = 2'b11;
//=============================================== 
//
//===============================================

endmodule


