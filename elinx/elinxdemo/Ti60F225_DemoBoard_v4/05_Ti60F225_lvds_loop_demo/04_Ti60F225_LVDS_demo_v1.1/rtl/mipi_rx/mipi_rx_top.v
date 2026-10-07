
module mipi_rx_top(
input		wire		rst_n,

input 				mipi_rx_clk_CLKOUT,
input 				mipi_rx_clk_LP_N_IN,
input 				mipi_rx_clk_LP_P_IN,
output 				mipi_rx_clk_HS_ENA,
output 				mipi_rx_clk_HS_TERM,
            	
input [7:0] 	mipi_rx_d0_HS_IN,
input 				mipi_rx_d0_LP_N_IN,
input 				mipi_rx_d0_LP_P_IN,
output 				mipi_rx_d0_HS_ENA,
output 				mipi_rx_d0_HS_TERM,
output 				mipi_rx_d0_RST,
            	
input [7:0] 	mipi_rx_d1_HS_IN,
input 				mipi_rx_d1_LP_N_IN,
input 				mipi_rx_d1_LP_P_IN,
output 				mipi_rx_d1_HS_ENA,
output 				mipi_rx_d1_HS_TERM,
output 				mipi_rx_d1_RST,
            	
input [7:0] 	mipi_rx_d2_HS_IN,
input 				mipi_rx_d2_LP_N_IN,
input 				mipi_rx_d2_LP_P_IN,
output 				mipi_rx_d2_HS_ENA,
output 				mipi_rx_d2_HS_TERM,
output 				mipi_rx_d2_RST,
            	
input [7:0] 	mipi_rx_d3_HS_IN,
input 				mipi_rx_d3_LP_N_IN,
input 				mipi_rx_d3_LP_P_IN,
output 				mipi_rx_d3_HS_ENA,
output 				mipi_rx_d3_HS_TERM,
output 				mipi_rx_d3_RST    ,
  
output 				pixel_data_valid,
output [63:0] pixel_data,
output [3:0] 	pixel_per_clk,
output [5:0] 	datatype,

input 				axi_rready,
output 				axi_rvalid,
output [31:0] axi_rdata,
output 				axi_arready,
input 				axi_arvalid,
input [5:0] 	axi_araddr,
input 				axi_bready,
output 				axi_bvalid,
output 				axi_wready,
input 				axi_wvalid,
input [31:0] 	axi_wdata,
output 				axi_awready,
input 				axi_clk,
input 				axi_reset_n,
input [5:0] 	axi_awaddr,
input 				axi_awvalid


);


(* async_reg = "true" *)reg		[3:0]r_mipi_rx_data_LP_P_IN_0_1P;
(* async_reg = "true" *)reg		[3:0]r_mipi_rx_data_LP_N_IN_0_1P;
(* async_reg = "true" *)reg		[3:0]r_mipi_rx_data_LP_P_IN_0_2P;
(* async_reg = "true" *)reg		[3:0]r_mipi_rx_data_LP_N_IN_0_2P;


(* async_reg = "true" *)reg		[31:0]r_mipi_rx_data_HS_IN_0_1P;
(* async_reg = "true" *)reg		[31:0]r_mipi_rx_data_HS_IN_0_2P;

//two pipeline
always@(posedge mipi_rx_clk_CLKOUT or negedge arst_n )
begin
		if (~i_arstn)
		begin
			r_mipi_rx_data_LP_P_IN_0_1P	<= 2'b0;
			r_mipi_rx_data_LP_N_IN_0_1P	<= 2'b0;
			r_mipi_rx_data_LP_P_IN_0_2P	<= 2'b0;
			r_mipi_rx_data_LP_N_IN_0_2P	<= 2'b0;
		end else begin
			r_mipi_rx_data_LP_P_IN_0_1P	<= {mipi_rx_d3_LP_P_IN,mipi_rx_d2_LP_P_IN,mipi_rx_d1_LP_P_IN, mipi_rx_d0_LP_P_IN}; 
			r_mipi_rx_data_LP_N_IN_0_1P	<= {mipi_rx_d3_LP_N_IN,mipi_rx_d2_LP_N_IN,mipi_rx_d1_LP_N_IN, mipi_rx_d0_LP_N_IN};
			r_mipi_rx_data_LP_P_IN_0_2P	<= r_mipi_rx_data_LP_P_IN_0_1P;
			r_mipi_rx_data_LP_N_IN_0_2P	<= r_mipi_rx_data_LP_N_IN_0_1P;
		end
end

always@( posedge mipi_rx_clk_CLKOUT or negedge arst_n )
begin
		if (~i_arstn) begin
			r_mipi_rx_data_HS_IN_0_1P	<= {16{1'b0}};
			r_mipi_rx_data_HS_IN_0_2P	<= {16{1'b0}};
		end else begin
			r_mipi_rx_data_HS_IN_0_1P	<= {mipi_rx_d3_HS_IN,mipi_rx_d2_HS_IN,mipi_rx_d1_HS_IN, mipi_rx_d0_HS_IN};
			r_mipi_rx_data_HS_IN_0_2P	<= r_mipi_rx_data_HS_IN_0_1P;
		end
end
wire [3:0] w_rx_d_HS_ENA;
assign	mipi_rx_d0_HS_TERM	= w_rx_d_HS_ENA[0];
assign	mipi_rx_d1_HS_TERM	= w_rx_d_HS_ENA[1];
assign	mipi_rx_d2_HS_TERM	= w_rx_d_HS_ENA[2];
assign	mipi_rx_d3_HS_TERM	= w_rx_d_HS_ENA[3];
assign	mipi_rx_d0_HS_ENA		= w_rx_d_HS_ENA[0];
assign	mipi_rx_d1_HS_ENA		= w_rx_d_HS_ENA[1];
assign	mipi_rx_d2_HS_ENA		= w_rx_d_HS_ENA[2];
assign	mipi_rx_d3_HS_ENA		= w_rx_d_HS_ENA[3];
assign	mipi_rx_d0_RST		= ~arst_n;
assign	mipi_rx_d1_RST		= ~arst_n;
assign	mipi_rx_d2_RST		= ~arst_n;
assign	mipi_rx_d3_RST		= ~arst_n;
//=======================================================
//
//=========================================================



mipi_rx_csi u_mipi_rx_csi(
.reset_n 							( arst_n 							),
.clk 									( clk 								),
.reset_byte_HS_n			( arst_n 							),
.clk_byte_HS 					( mipi_rx_clk_CLKOUT 	),
.reset_pixel_n 				( arst_n 							),
.clk_pixel 						( i_mipi_rx_clk 			),
.Rx_LP_CLK_P 					( mipi_rx_clk_LP_P_IN ),
.Rx_LP_CLK_N 					( mipi_rx_clk_LP_N_IN ),
.Rx_HS_enable_C 			( mipi_rx_clk_HS_ENA 	),
.LVDS_termen_C 				( mipi_rx_clk_HS_TERM ),
                			
.Rx_LP_D_P 						( r_mipi_rx_data_LP_P_IN_0_2P ),
.Rx_LP_D_N 						( r_mipi_rx_data_LP_P_IN_0_2N ),
.Rx_HS_D_0 						( r_mipi_rx_data_HS_IN_0_2P[ 7: 0] ),
.Rx_HS_D_1 						( r_mipi_rx_data_HS_IN_0_2P[15: 8] ),
.Rx_HS_D_2 						( r_mipi_rx_data_HS_IN_0_2P[23:16] ),
.Rx_HS_D_3 						( r_mipi_rx_data_HS_IN_0_2P[31:24] ),
.Rx_HS_D_4 						(  ),
.Rx_HS_D_5 						(  ),
.Rx_HS_D_6 						(  ),
.Rx_HS_D_7 						(  ),
.Rx_HS_enable_D 			( w_rx_d_HS_ENA ),
.LVDS_termen_D 				( LVDS_termen_D ),
.fifo_rd_enable 			(  ),
.fifo_rd_empty 				(  ),
.DLY_enable_D 				(  ),
.DLY_inc_D 						(  ),
.u_dly_enable_D 			(  ),
.u_dly_inc_D 					( u_dly_inc_D ),

.irq 									(  ),
.pixel_data_valid 		(w_dp_rx_valid  ),
.pixel_data 					(w_dp_rx_data  ),
.pixel_per_clk 				(  ),
.datatype 						( w_dp_rx_dt ),
.shortpkt_data_field 	(  ),
.word_count 					(  ),
.vcx 									(  ),
.vc 									(  ),
.hsync_vc0 						(  ),
.hsync_vc1 						(  ),
.hsync_vc2 						(  ),
.hsync_vc3 						(  ),
.hsync_vc4 						(  ),
.hsync_vc5 						(  ),
.hsync_vc6 						(  ),
.hsync_vc7 						(  ),
.hsync_vc8 						(  ),
.hsync_vc9 						(  ),
.hsync_vc10 					(  ),
.hsync_vc11 					(  ),
.hsync_vc12 					(  ),
.hsync_vc13 					(  ),
.hsync_vc15 					(  ),
.hsync_vc14 					(  ),

.vsync_vc0 						(  ),
.vsync_vc1 						(  ),
.vsync_vc2 						(  ),
.vsync_vc3 						(  ),
.vsync_vc4 						(  ),
.vsync_vc5 						(  ),
.vsync_vc6 						(  ),
.vsync_vc7 						(  ),
.vsync_vc8 						(  ),
.vsync_vc9 						(  ),
.vsync_vc10 					(  ),
.vsync_vc11 					(  ),
.vsync_vc12 					(  ),
.vsync_vc13 					(  ),
.vsync_vc14 					(  ),
.vsync_vc15 					(  ),

.axi_clk 							( axi_clk 		),      
.axi_reset_n 					( axi_reset_n ),  
.axi_rready 					( axi_rready 	),
.axi_rvalid 					( axi_rvalid 	),
.axi_rdata 						( axi_rdata 	),
.axi_arready 					( axi_arready ),
.axi_arvalid 					( axi_arvalid ),
.axi_araddr 					( axi_araddr 	),
.axi_bready 					( axi_bready 	),
.axi_bvalid 					( axi_bvalid 	),
.axi_wready 					( axi_wready 	),
.axi_wvalid 					( axi_wvalid 	),
.axi_wdata 						( axi_wdata 	),
.axi_awready 					( axi_awready ),
.axi_awaddr 					( axi_awaddr 	),
.axi_awvalid 					( axi_awvalid )
);


endmodule