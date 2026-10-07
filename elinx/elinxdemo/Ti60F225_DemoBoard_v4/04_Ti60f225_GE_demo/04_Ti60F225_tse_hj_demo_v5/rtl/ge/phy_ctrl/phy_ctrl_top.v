
module phy_ctrl_top(
	
	
  input RST_N,
  input ETH_MDIO_IN,
  input clk_25m,
  output ETH_MDC,
  output ETH_MDIO_OUT,
  output ETH_MDIO_OE
  
  );

reg	rd_en =0;
reg	wr_en = 0;

wire	[4:0] reg_addr;
reg	[8:0] cnt =0; 
wire		rd_valid;
wire		busy;
wire			[15:0] wr_data;  
wire 	[15:0] rd_data;
wire [5:0] bit_cnt;
wire		RST_N;     
reg		[5:0] addr;
reg	busy_d0 ;
wire neg_busy = {busy_d0,busy} == 2'b10;
wire 	wr_rd_en;
reg [5:0] dly_cnt ;
reg [22:0] dly_1s_cnt;
always @( posedge clk_25m or negedge RST_N)
begin
		if( !RST_N ) begin
				cnt <= 'd0;
				rd_en <= 1'b0;
				wr_en <= 1'b0;
				addr <= 'd0;    
				dly_cnt <= 'd0;
		end else  begin
		
				case( cnt[1:0] )
				0 : begin
							cnt <= cnt + 1'b1;    
							dly_cnt <= 'd0;  
							dly_1s_cnt <=  'd0;
				end
				
				1 : begin
							
							cnt <= cnt + 1'b1;
								if( wr_rd_en ) begin
									rd_en <= 1'b1;
									wr_en <= 1'b0;
							end else begin
									rd_en <= 1'b0;
									wr_en <= 1'b1;
							end
				end
				2 : begin   
						rd_en <= 1'b0;
						wr_en <= 1'b0;
						if( neg_busy ) begin           
								cnt <= cnt + 1'b1;  
						end			
				end    
				3 : begin
						if( cnt[8:2] == 63 )  begin
								if( &dly_1s_cnt ) begin
										addr <= addr + 1'b1; 
										cnt <= cnt + 1'b1;
								end else begin
										dly_1s_cnt <= dly_1s_cnt + 1'b1;
								end
								
						end else if( cnt[8:2] == 127 )
								cnt <= cnt;
						else begin 
								if( &dly_cnt  ) begin
										cnt <= cnt + 1'b1;
										addr <= addr + 1'b1;
										dly_cnt <= 'd0;
								end else begin
										dly_cnt <= dly_cnt + 1'b1;
								end
						end
				end
				
				default:;
				endcase
		end 
end

	user_rom #(

) u_user_rom (
    /*i*/.clock			( clk_25m ),
    /*i*/.addr_ptr	( addr 		),
    /*o*/.rdata_out ( {wr_data,wr_rd_en})
);




	assign reg_addr = cnt[6:2];
  phy_ctrl u_phy_ctrl(
	/*i*/.clk				(clk_25m),
	/*i*/.rst_n			(RST_N),
	/*i*/.wr_en			(wr_en),
	/*i*/.rd_en			(rd_en),
	/*i*/.phy_addr	(5'h03),
	/*i*/.reg_addr	(reg_addr), 
	/*i*/.wr_data		(wr_data),
	/*o*/.busy			(busy),
				.rd_valid (rd_valid),
				.rd_data  (rd_data),   
				.cnt			(bit_cnt),            	
	/*o*/.MDC				(ETH_MDC			),
	/*o*/.MDIO_OUT	(ETH_MDIO_OUT ),
	/*o*/.MDIO_IN		(ETH_MDIO_IN	),
	/*o*/.MDIO_OE 	(ETH_MDIO_OE  )
	
	);
	
	always @( posedge clk_25m )
	begin
			busy_d0 <= busy;
	end
	



endmodule