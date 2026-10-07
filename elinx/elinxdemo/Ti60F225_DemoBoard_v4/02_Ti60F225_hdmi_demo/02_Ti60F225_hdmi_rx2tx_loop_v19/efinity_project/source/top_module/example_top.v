
//`define Efinity_Debug
//`define AXI_FULL_DEPLEX
module example_top
(

// clk interface
input sys_clk,
input osc_clk,
output osc_en,

// hdmi interface

  output tmds_tx_clk_TX_OE,
  output [9:0] tmds_tx_clk_TX_DATA,
  output tmds_tx_clk_TX_RST,
  output tmds_tx_data0_TX_OE,
  output [9:0] tmds_tx_data0_TX_DATA,
  output tmds_tx_data0_TX_RST,
  output tmds_tx_data1_TX_OE,
  output [9:0] tmds_tx_data1_TX_DATA,
  output tmds_tx_data1_TX_RST,
  output tmds_tx_data2_TX_OE,
  output [9:0] tmds_tx_data2_TX_DATA,
  output tmds_tx_data2_TX_RST,
  
  input 			hdmi_rx_slow_clk,
  input 			hdmi_rx_clk_RX_DATA,
  input [9:0] 		hdmi_rx_d0_RX_DATA,
  input [9:0] 		hdmi_rx_d1_RX_DATA,
  input [9:0] 		hdmi_rx_d2_RX_DATA,
  output 			hdmi_rx_clk_RX_ENA,
  output 			hdmi_rx_d0_RX_RST,
  output 			hdmi_rx_d0_RX_ENA,
  output 			hdmi_rx_d1_RX_RST,
  output 			hdmi_rx_d1_RX_ENA,
  output 			hdmi_rx_d2_RX_RST,
  output 			hdmi_rx_d2_RX_ENA,   
  output 			hdmi_rx_clk_RX_DLY_INC,
  output 			hdmi_rx_clk_RX_DLY_ENA,
  output 			hdmi_rx_clk_RX_DLY_RST,
  input hdmi_rx_pll_LOCKED ,
  output hdmi_rx_pll_RSTN,
  output 	HPD_N,
  input 	HDMI_5V_N,
  input 	FPGA_HDMI_SCL_IN,
  input 	FPGA_HDMI_SDA_IN,
  output 	FPGA_HDMI_SCL_OUT,
  output 	FPGA_HDMI_SCL_OE,
  output 	FPGA_HDMI_SDA_OUT,
  output 	FPGA_HDMI_SDA_OE,

//ddr3
 output DDR3_PLL_RSTN,
  output SYS_PLL_RSTN,
  input DDR3_PLL_LOCK,
  input SYS_PLL_LOCK,




output [2:0]			shift,
output [4:0]			shift_sel,
output 					shift_ena,

// led 
	input nrst,
	input hdmi_sel,
	input clk_10m,
	output [1:0] b_led


);
//=====================================================================
////Define  Parameter
//=====================================================================

  /////////////   
  	parameter   AXI_DATA_WIDTH    = 128               ; //AXI Data Width(Bit)
  
  	parameter   DDR_WRITE_FIRST   = 1'h1              ; //1:Write First ; 0: Read First   
  	parameter   AXI_ID_WIDTH    =   8         ;
   //Define  Parameter
  /////////////////////////////////////////////////////////                                
	
	localparam   AXI0_WR_ID        = 8'haa           ; //AXI Write ID
	localparam   AXI0_RD_ID        = 8'h55           ; //AXI Read ID	
		  	
	localparam   AXI_ADDR_WIDTH 	= 32;//Address Width      
	localparam   S_COUNT 					= 1;                          
	localparam   M_COUNT 					= 1;                          
	localparam   AXI_SW 					= AXI_DATA_WIDTH/8;//Write Strobes Width     
	
	localparam H_PRE_PORCH   	= 13'd88 	;//	
	localparam H_SYNC 	 		= 13'd44 	;//
	localparam H_VALID 	 	  	= 13'd1920;//
	localparam H_BACK_PORCH  	= 13'd148 ;// 	
	localparam V_PRE_PORCH   	= 13'd4 	;//	
	localparam V_SYNC 	 	    = 13'd5 	;//
	localparam V_VALID 	 	  	= 13'd1080 ;//
	localparam V_BACK_PORCH  	= 13'd36 	;//	

  /////////////                 
//=========================================================================
//signal define
//=========================================================================


//==============================================================================
//reset porcess module
//==============================================================================
 assign DDR3_PLL_RSTN = nrst;
 assign SYS_PLL_RSTN = nrst;

 reg   [3:0]   Reset_Cnt     = 4'h0  ;
 wire          DdrResetCtrl  ;
 wire		   Sys_Rst_N	;
 wire         pll_rst_n;

  always  @(posedge sys_clk )
  begin
    if (~DDR3_PLL_LOCK)          Reset_Cnt   <= 3'h0  ;
    else if (~SYS_PLL_LOCK)    Reset_Cnt   <= 3'h0  ;
    else if (~&Reset_Cnt)   Reset_Cnt   <= Reset_Cnt + 4'h1  ;
  end

  assign  Sys_Rst_N  = Reset_Cnt[3]  ;
  wire    rst_n = Sys_Rst_N;


  assign osc_en = 1'b1;
	reg [25:0] cnt = 'd0;
  always @( posedge sys_clk )
  begin
		cnt <= cnt + 1'b1;
		
  end
reg [25:0]  hdmi_led_cnt ;
  always @( posedge hdmi_rx_slow_clk)
  begin
		hdmi_led_cnt <= hdmi_led_cnt+ 1'b1;
  end
  assign b_led[0] = cnt[25];//run led
  assign b_led[1] =hdmi_led_cnt[25];

//   always @( posedge sys_clk )
//   begin
// 	hdmi_sel
//   end 
//=====================================================================================
//hdmi demo
//=====================================================================================
// wire                            video_hs;
// wire                            video_vs;
// wire                            video_de;
// wire[7:0]                       video_r;
// wire[7:0]                       video_g;
// wire[7:0]                       video_b;


wire 			                      rx_hsync;	
wire 			                      rx_vsync;	
wire 			                      rx_de	 ;  
wire [7:0]                      rdata_in;	
wire [7:0]                      gdata_in;	
wire [7:0]                      bdata_in;




	wire     [23:0]					audio_L ;
wire     [23:0]					audio_R ;
wire           					audio_valid;
wire           					audio_param_valid ;
wire           					audio_max_word_length;     
wire [2:0]     					audio_state;          
wire [3:0]     					audio_ch;            
wire [3:0]     					audio_samp_freq;     
wire [2:0]     					audio_samp_word_len;
wire [1:0]              video_format;

assign hdmi_rx_clk_RX_ENA = 1'b1;

assign hdmi_rx_d0_RX_ENA = 1'b1; 
assign hdmi_rx_d1_RX_ENA = 1'b1;  
assign hdmi_rx_d2_RX_ENA = 1'b1; 
 

assign hdmi_rx_d0_RX_RST = 1'b0; 
assign hdmi_rx_d1_RX_RST = 1'b0;
assign hdmi_rx_d2_RX_RST = 1'b0;  

assign tmds_tx_data0_TX_OE = 1'b1;
assign tmds_tx_data1_TX_OE = 1'b1;
assign tmds_tx_data2_TX_OE = 1'b1;
assign tmds_tx_clk_TX_OE   = 1'b1;

assign tmds_tx_data0_TX_RST = 1'b0;
assign tmds_tx_data1_TX_RST = 1'b0;
assign tmds_tx_data2_TX_RST = 1'b0;
assign tmds_tx_clk_TX_RST   = 1'b0;


//================================================
//
//================================================
reg [22:0] wait_cnt;
reg [22:0] lock_wait_cnt ;
always @( posedge osc_clk )
begin
	if( ~HPD_N )
		if( wait_cnt[22]) begin 
			wait_cnt <= wait_cnt;
		end else
			wait_cnt <= wait_cnt + 1'b1;
	else 
		wait_cnt <= 0;	
end 

always @( posedge osc_clk )
begin
	if( ~hdmi_rx_pll_LOCKED )
		if( lock_wait_cnt[20]) 
			lock_wait_cnt <= 'd0;
		else 
			lock_wait_cnt <= lock_wait_cnt + 1'b1;
	else 
		lock_wait_cnt <= 'd0;
end


  assign  hdmi_rx_pll_RSTN   = wait_cnt[22] & (~lock_wait_cnt[20]) & nrst & pll_rst_n;

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

/*i*/.pclk          	(hdmi_rx_slow_clk),         // double rate pixel clock                
/*i*/.bdata        		(~hdmi_rx_d0_RX_DATA),       // Blue data in                           
/*i*/.gdata       		(~hdmi_rx_d1_RX_DATA),       // Green data in                          
/*i*/.rdata         	(~hdmi_rx_d2_RX_DATA),       // Red data in                            
/*i*/.pll_lock        (hdmi_rx_pll_LOCKED),//   (rst_n          	  ),       //// external reset input, e.g. reset button
/*O*/.pll_rst_n       (pll_rst_n),
/*o*/.hsync         	(rx_hsync			  ),                // hsync data                             
/*o*/.vsync         	(rx_vsync			  ),                // vsync data                             
/*o*/.de            	(rx_de				  ),                // data enable                            
/*o*/.red           	(rdata_in			  ),                // pixel data out                         
/*o*/.green         	(gdata_in			  ),                // pixel data out                         
/*o*/.blue          	(bdata_in			  ),                 // pixel data out   
/*o*/.DLY_INC			(hdmi_rx_clk_RX_DLY_INC),
/*o*/.DLY_RST			(hdmi_rx_clk_RX_DLY_RST),
/*o*/.DLY_ENA			(hdmi_rx_clk_RX_DLY_ENA),
.audio_L                (audio_L              ),
.audio_R                (audio_R              ),
.audio_valid            (audio_valid          ),
.audio_param_valid      (audio_param_valid    ),
.audio_max_word_length  (audio_max_word_length),     
.audio_stae             (audio_stae           ),          
.audio_ch               (audio_ch             ),            
.audio_samp_freq        (audio_samp_freq      ),     
.audio_samp_word_len    (audio_samp_word_len  ),
.avi_infoframe_S   		(),
.avi_infoframe_B   		(),
.avi_infoframe_A   		(),
.avi_infoframe_Y   		(video_format),
.avi_infoframe_R   		(),
.avi_infoframe_M   		(),
.avi_infoframe_C   		(),
.avi_infoframe_SC  		(),
.avi_infoframe_Q   		(),
.avi_infoframe_EC  		(),
.avi_infoframe_ITC 		(),
.avi_infoframe_VIC 		(),
.avi_infoframe_PR  		(),
.avi_infoframe_CN  		(),
.avi_infoframe_YQ  		(),
.avi_infoframe_ETB 		(),
.avi_infoframe_SBB 		(),
.avi_infoframe_ELB 		(),
.avi_infoframe_SRB      ()               
                                                                                
   );    // pixel data out   

   vid_info_det vid_info_det_inst (
    .clk(hdmi_rx_slow_clk),
    .rst_n(rst_n),
    .i_vs(rx_vsync),
    .i_hs(rx_hsync),
    .i_de(rx_de),
    .frame_cnt_o(frame_cnt_o),
    .frame_stable(frame_stable),
    .negtive_sync(negtive_sync),
    .ddr_frame_len(ddr_frame_len),
    .h_act(h_act),
    .h_active_error(h_active_error),
    .v_act(v_act),
    .v_total(v_total),
    .h_total(h_total)
  );
          
//==================================================================
//
//==================================================================

/*
	  color_bar color_bar_m0(
	.clk(hdmi_rx_slow_clk),
	.rst(~rst_n),
	.hs(video_hs),
	.vs(video_vs),
	.de(video_de),
	.rgb_r(video_r),
	.rgb_g(video_g),
	.rgb_b(video_b)
);*/

wire [9:0] tmds_data0;
wire [9:0] tmds_data1;
wire [9:0] tmds_data2;
wire [9:0] tmds_clk ;


dvi_encoder dvi_encoder_m0
(
	.pixelclk      		(hdmi_rx_slow_clk          ),// system clock
	.rst_p         		((~rst_n)            ),// reset
	.i_bdata      		(bdata_in	),   ////   (video_b            ),//
	.i_gdata     		  (gdata_in	),   ////(video_g            ),//   
	.i_rdata       		(rdata_in	),   ////(video_r            ),//   
	.i_hs         		(rx_hsync	),   ////(video_hs           ),//   
	.i_vs         		(rx_vsync	),   //// (video_vs           ),//  
	.i_de            	(rx_de		),   //  // (video_de           ),//
  .video_format     (video_format), //// 00 = RGB, 01 = YCbCr 4:2:2, 10 = YCbCr 4:4:4
  .video_VIC        (0),
	.audio_L			    (audio_L),
  .audio_R			    (audio_R),
  .audio_valid		  (audio_valid),
  .audio_N                (6144),     //(20'h01880),//     
  .audio_CTS              (148500),      //(20'h28488),//      
  .audio_sample_frequency (audio_samp_freq),    //(3'b000),// 
  .audio_word_length      ({audio_samp_word_len,audio_max_word_length}),//(4'b1011),//

	.tmds_data0    		(tmds_data0),
  .tmds_data1    		(tmds_data1),
  .tmds_data2    		(tmds_data2),
  .tmds_clk      	  (tmds_clk  )
);
assign tmds_tx_clk_TX_DATA   = ~tmds_clk;
assign tmds_tx_data0_TX_DATA = ~tmds_data0;
assign tmds_tx_data1_TX_DATA = ~tmds_data1;
assign tmds_tx_data2_TX_DATA = ~tmds_data2;



//=================================================================================
//
//=================================================================================
//=============================================================
//
//=============================================================
//=============================================================
//
//=============================================================
// wire [7:0]	rx_data  ;
// wire 				rx_valid ;
// wire [7:0]	tx_data  ;
// wire 				tx_valid ;
// wire 				tx_req   ;
// wire	[9:0]	ctrl_time	;
// wire[199:0]	ctrl_io  	;
// wire				time_valid;
// wire				io_valid  ;
// reg		[7:0] rst_cnt = 'd0;

// 	uart_top #(
// 			.CLK_RATE 		( 32'd10000000),
// 			.BPS_RATE 		( 115200		),
// 			.STOP_BIT_W 	( 2'b00			),//00: stop_bit = 1; 01: stop_bit = 1.5 ; 10 : stop_bit = 2
// 			.CHECKSUM_MODE( 2'b00			),//00:space, 01:odd ,10:even ,11:mask    
// 			.CHECKSUM_EN 	( 1'b0    	)
// 	)u_uart_top(
// 		/*i*/.clk					(clk_10m),
// 		/*i*/.rst_n				(rst_n	),
// 	  /*i*/.rxd					(uart_rx),
// 	  /*o*/.txd					(uart_tx),
// 	  /*o*/.rx_data			(rx_data ),
// 	  /*o*/.rx_valid		(rx_valid),
// 	  /*i*/.tx_data			(tx_data ),
// 		/*i*/.tx_valid		(tx_valid),
// 		/*o*/.tx_req  		(tx_req  )
// );


//  uart_parse u_uart_parse(
// 		/*i*/.clk					(clk_10m),
// 		/*i*/.rst_n				(rst_n ),
// 		/*i*/.rx_valid		(rx_valid),
// 		/*i*/.rx_data			(rx_data ),
// 		/*o*/.tx_valid		(tx_valid),
// 		/*o*/.tx_data			(tx_data ),
// 		/*i*/.tx_req  		(tx_req  ),
// 		/*o*/.ctrl_time		(ctrl_time	),
//     /*o*/.ctrl_io  		(ctrl_io  	),
//     /*o*/.time_valid	(time_valid ),
//     /*o*/.io_valid  	(io_valid   )  
// );


endmodule