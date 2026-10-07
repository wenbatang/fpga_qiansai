

module phy_ctrl(
	input		wire		clk,
	input		wire		rst_n,
	input		wire		wr_en,
	input		wire		rd_en,
	input		wire	[4:0] phy_addr,
	input		wire		[4:0] reg_addr,   
	input		wire	[15:0]	wr_data,
	output	wire		busy,    
	
	output	reg					rd_valid,
	output	reg	[15:0]	rd_data,
	output	reg	[5:0] cnt = 0,
	
	output	wire			MDC,
	output	wire		MDIO_OUT,
	input		wire		MDIO_IN,
	output	reg			MDIO_OE
	
	
	
);
//       assign MDC = ~clk;
	localparam START = 2'b01;
	localparam WR_OPCODE = 2'b01;
	localparam RD_OPCODE = 2'b10;
	localparam WR_TR = 2'b10;
	localparam RD_TR = 2'b00;
	
	reg	[31:0] data_reg;
	reg	wr_high;
	wire	 data_catpure ;
	
	
	assign busy = |cnt;
	always @( posedge clk or negedge rst_n )
	begin
			if( !rst_n )
					cnt <= 0;
			else if( wr_en | rd_en )
					cnt <= 1;
			else if( cnt[5] )
					cnt <= 'd0;
			else
					cnt <= cnt + |cnt;
	end
	assign data_capture = busy ? 1'b0 : (wr_en | rd_en)  ;
	always @( posedge clk )
	begin
			if( data_capture ) begin
						data_reg <= wr_en ? {START,WR_OPCODE,phy_addr,reg_addr,WR_TR,wr_data} : {START,RD_OPCODE,phy_addr,reg_addr,RD_TR,16'd0};
			end else 
						data_reg <= |cnt ? {data_reg[30:0],1'b0} : 0;
					
	end
	assign MDIO_OUT = data_reg[31];
	always @( posedge clk )
	begin
			if( data_capture )
					wr_high <= wr_en ? 1'b1 : 1'b0;
	end
	 
	   
	
	always @( posedge clk or negedge rst_n )
	begin
			if ( !rst_n )
					MDIO_OE <= 1'b0;
			else if( data_capture )
					MDIO_OE <= 1'b1;
			else if( |cnt[4:0] )
					if( wr_high )
							MDIO_OE <= 1'b1 ; 
					else if(cnt <14)
							MDIO_OE <= 1'b1;
					else if( cnt == 15 )
							MDIO_OE <= 1'b1;
					else
							MDIO_OE <= 1'b0;
						
			else
					MDIO_OE <= 1'b0;
					
	end
	
	always @( posedge clk )
	begin
			if( cnt > 16 )
				rd_data <= {rd_data[14:0],MDIO_IN};
	end
	
	always @( posedge clk )
	begin
			if( cnt[5] & (~wr_high ))
					rd_valid <= 1'b1;
			else
					rd_valid <= 1'b0;
	end
	

	


endmodule