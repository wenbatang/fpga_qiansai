// -----------------------------------------------------------------------------
// Copyright (c) 2014-2019 All rights reserved
// -----------------------------------------------------------------------------
// Author : Youkaiyuan  v3eduyky@126.com
// wechat : 15921999232
// File   : timer.v
// Create : 2019-11-01 20:04:29
// Revise : 2019-11-01 20:19:24
// Editor : sublime text3, tab size (4)
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps

module timer #(
	parameter	SIM_FLAG = 0
	)
	(
	input	wire 		tx_clk,
	input	wire 		rst,
	output	wire 		timer_pulse
    );

parameter ONE_S = 1249999;
parameter SIM_V = 2047;

reg [26:0] 	timer_cnt;
reg 		timer_pulse_r;

assign timer_pulse = timer_pulse_r;

always @(posedge tx_clk) begin
	if (rst == 1'b1) begin
		timer_cnt <= 'd0;
	end
	else if (SIM_FLAG == 1'b0) begin
		if(timer_cnt == ONE_S) begin
			timer_cnt <='d0;
		end
		else begin
			timer_cnt <= timer_cnt + 1'b1;
		end
	end
	else begin
		if(timer_cnt == SIM_V)begin
			timer_cnt <='d0;
		end
		else begin
			timer_cnt <= timer_cnt + 1'b1;
		end
	end
end


always @(posedge tx_clk) begin
	if (rst == 1'b1) begin
		timer_pulse_r <=1'b0;
	end
	else if (SIM_FLAG == 1'b1 && timer_cnt == SIM_V) begin
		timer_pulse_r <= 1'b1;
	end
	else if(SIM_FLAG == 1'b0 && timer_cnt == ONE_S) begin
		timer_pulse_r <= 1'b1;
	end
	else begin
		timer_pulse_r <= 1'b0;
	end
end


endmodule
