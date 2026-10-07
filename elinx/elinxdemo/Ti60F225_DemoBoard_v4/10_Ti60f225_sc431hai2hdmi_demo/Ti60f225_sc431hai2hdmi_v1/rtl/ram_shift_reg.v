/////////////////////////////////////////////////////////////////////////////
//
// Copyright (C) 2013-2018 Efinix Inc. All rights reserved.
//
// Unsigned Multiplier
//
// *******************************
// Revisions:
// 0.0 Initial rev
// *******************************

module ram_shift_reg
#(
	parameter	DATA_WIDTH	= 10,
	parameter	LATENCY		= 20,
	parameter	NUM_GROUP	= 1		// TODO
)
(
	input	arst,
	input	clk,
	
	input	[DATA_WIDTH-1:0]sr_in,
	input	[8:0]i_tape,
	
	output	[DATA_WIDTH-1:0]sr_out,
	output	[DATA_WIDTH-1:0]tg_out
);

reg		r_we_1P;
reg		[8:0]r_waddr_1P;

reg		r_re_1P;
reg		[8:0]r_raddr_1P;

wire	[DATA_WIDTH-1:0]w_rdata;

always@(posedge arst or posedge clk)
begin
	if (arst)
	begin
		r_we_1P		<= 1'b0;
		r_waddr_1P	<= {9{1'b0}};
		
		r_re_1P		<= 1'b0;
		r_raddr_1P	<= {9{1'b0}};
	end
	else
	begin
		r_we_1P		<= 1'b1;
//		if (r_we_1P)
			r_waddr_1P	<= r_waddr_1P+1'b1;
		
		if (r_waddr_1P == LATENCY-2)
			r_re_1P	<= 1'b1;
		if (r_re_1P)
			r_raddr_1P	<= r_raddr_1P+1'b1;
	end
end

simple_dual_port_ram
#(
	.DATA_WIDTH(DATA_WIDTH),
	.ADDR_WIDTH(9),
	.OUTPUT_REG("FALSE"),
	.RAM_INIT_FILE("")
)
inst_simple_dual_port_ram
(
	.wdata(sr_in),
	.waddr(r_waddr_1P+i_tape),
	.raddr(r_raddr_1P),
	.we(r_we_1P),
	.wclk(clk),
	.re(r_re_1P),
	.rclk(clk),
	.rdata(w_rdata)
);

assign	sr_out	= w_rdata;
assign	tg_out	= w_rdata;

endmodule
