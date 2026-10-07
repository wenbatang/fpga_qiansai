`timescale 1 ps / 1ps
module dvi_encoder
(
	input           pixelclk,       // system clock
	input           rst_p,          // reset
	input[7:0]      i_bdata,       // Blue data in
	input[7:0]      i_gdata,      // Green data in
	input[7:0]      i_rdata,        // Red data in
	input           i_hs,          // hsync data
	input           i_vs,          // vsync data
	input           i_de,             // data enable
	input     [ 1:0] video_format,
	input 	  [ 6:0] video_VIC,
	input     [23:0] audio_L ,
	input     [23:0] audio_R ,
	input            audio_valid,
	input  [19:0]    audio_N,
	input  [19:0]    audio_CTS,
	input [3:0]      audio_sample_frequency,     
	input [3:0]      audio_word_length,

	output          [9:0]tmds_data0,
    output          [9:0]tmds_data1,
    output          [9:0]tmds_data2,
    output          [9:0]tmds_clk

);

//Encryption begin
/*----------------------------------------------------------------------------------*\
                                 The main code
\*----------------------------------------------------------------------------------*/

localparam S_IDLE 			= 3'd0;
localparam S_CTRL 			= 3'd1;
localparam S_PRE_IS 		= 3'd2;
localparam S_LID_GB 		= 3'd3;
localparam S_DATA_IS 		= 3'd4;
localparam S_POST_DATA_IS 	= 3'd5;
localparam S_TRA_GB 		= 3'd6;
localparam S_PRE_VID 		= 3'd7;
reg [2:0] pre_state 		= 'd0;
reg [2:0] nx_state 		= 'd0;
reg [7:0] cnt 			= 'd0;//
reg [5:0] post_cnt 		= 'd0;
reg control_period 		= 1'b0;
reg island_preamble 	= 'd0;
reg island_lead_gb 		= 1'b0;
reg data_island_period 	= 1'b0;
reg island_trail_gb 	= 1'b0;
reg video_preamble 		= 1'b0;
reg video_lead_gb 		= 1'b0;
wire    [9:0]   red ;
wire    [9:0]   green ;
wire    [9:0]   blue ;

reg [5:0] waddr = 'd0;
reg [5:0] raddr = 'd0;
wire [7:0] ram_b_dat ;
wire [7:0] ram_g_dat ;
wire [7:0] ram_r_dat ;
wire       ram_hs;
wire  	   ram_vs;
wire       ram_de;
simple_dual_port_ram # (
    .DATA_WIDTH(27),
    .ADDR_WIDTH(6),
    .OUTPUT_REG("FALSE"),
    .RAM_INIT_FILE("")
  )
  simple_dual_port_ram_inst (
    .wdata({i_bdata,i_gdata,i_rdata,i_hs,i_vs,i_de}),
    .waddr(waddr),
    .raddr(raddr),
    .we(1'b1),
    .wclk(pixelclk),
    .re(1'b1),
    .rclk(pixelclk),
    .rdata({ram_b_dat,ram_g_dat,ram_r_dat,ram_hs,ram_vs,ram_de})
  );


  always @( posedge pixelclk )
  begin
		waddr <= waddr + 1'b1;
		raddr <= waddr + 12;
  end
  reg ctrl_time = 'd0;
  reg ctrl_time_ram = 'd0;
  always @( posedge pixelclk )
  begin
		ctrl_time <= ~i_de;
		ctrl_time_ram <= ~ram_de;
  end
  wire real_ctrl_time = ctrl_time & ctrl_time_ram;
  wire post_ctlr_time = real_ctrl_time ^ ctrl_time_ram;

  always @( posedge pixelclk )
  begin
		if( ctrl_time_ram )//( real_ctrl_time | post_ctlr_time)
			pre_state <= nx_state;
		else 
			pre_state <= S_IDLE;
  end

  always @( * )
  begin
		if( ctrl_time_ram )begin //( real_ctrl_time | post_ctlr_time ) begin
			case( pre_state )
			S_IDLE : begin
				nx_state 			= S_CTRL;
			end
			S_CTRL    : begin //=1
				if( post_ctlr_time)
					nx_state 		= S_PRE_VID;
				else if( cnt == 7 )  
					nx_state 		= S_PRE_IS;
				else 
					nx_state  		= S_CTRL;
			end
			S_PRE_IS  : begin //=2
				if( cnt == 7 ) 
					nx_state 		= S_LID_GB;
				else
					nx_state 		= S_PRE_IS;
			end
			S_LID_GB  : begin 
				if( cnt == 1 )
					nx_state 		= S_DATA_IS;
				else 
					nx_state 		= S_LID_GB;
			end 
			S_DATA_IS : begin //data Island
				if( &cnt[4:0] && post_ctlr_time )
					nx_state 		= S_TRA_GB;//6
				else if( &cnt )
					nx_state 		= S_TRA_GB;//6
				else if( ~real_ctrl_time )
					nx_state 		= S_POST_DATA_IS;//5
				else 
					nx_state 		= S_DATA_IS;//4
			end
			S_POST_DATA_IS : begin 
				if( &cnt[4:0] )
					nx_state 		= S_TRA_GB ;
				else
					nx_state 		= S_POST_DATA_IS;
			end 
			S_TRA_GB  : begin 
				if( cnt == 1 ) begin
					if( post_ctlr_time)
						nx_state 	=  S_PRE_VID;
					else 
						nx_state 	= S_CTRL;//1
				end else begin
					nx_state = S_TRA_GB;
				end
			end
			S_PRE_VID : begin 
				if( ~post_ctlr_time )
					nx_state 		=  S_IDLE ;
				else 
					nx_state 		= S_PRE_VID;
			end
			default: begin
				nx_state 			= S_IDLE;
			end
			endcase
		end else begin
			nx_state 				= S_IDLE;
		end
  end
  always @( posedge pixelclk )
  begin
		if( ctrl_time_ram )begin //( real_ctrl_time | post_ctlr_time ) begin
			island_lead_gb 		<= 1'b0;
			data_island_period  <= 1'b0;
			island_trail_gb 	<= 1'b0;
			control_period 		<= 1'b0;
			island_preamble 	<= 1'b0;
			cnt 				<= 'd0;
			video_preamble 		<= 1'b0;
			video_lead_gb		<= 1'b0;
			case( pre_state )
			S_IDLE : begin
				control_period 		<= 1'b1;
			end
			S_CTRL    : begin //=1
				if( cnt == 7 ) begin 
					cnt 			<= 'd0;
				end else begin
					cnt 			<= cnt + 1'b1;
				end
				control_period 		<= 1'b1;
			end
			S_PRE_IS  : begin //=2 preamble
				if( cnt == 7 ) begin
					cnt 			<= 'd0;
				end else begin
					cnt 			<= cnt + 1'b1;
				end
				island_preamble 	<= 1'b1;
			end
			S_LID_GB  : begin 
				island_lead_gb 		<= 1'b1;
				cnt 				<= cnt == 1 ? 0 : cnt + 1'b1;
			end 
			S_DATA_IS : begin 
				data_island_period  <= 1'b1;
				if( &cnt[4:0] && post_ctlr_time )
					cnt 			<= 'd0;
				else if( &cnt )
					cnt 			<= 'd0;
				else 
					cnt 			<= cnt + 1'b1;
				
			end
			S_POST_DATA_IS : begin 
				data_island_period  <= 1'b1;
				if( &cnt[4:0] )
					cnt 			<= 'd0;
				else 
					cnt 			<= cnt + 1'b1;
			end 
			S_TRA_GB  : begin 
				cnt 				<= cnt == 1 ? 0 : cnt + 1'b1;
				island_trail_gb 	<= 1'b1;
			end
			S_PRE_VID : begin 
				// control_period 		<= 'd0;
				// island_preamble 	<= 1'b0;
				if( post_cnt > 42 && post_cnt <= 50)
					video_preamble 	<= 1'b1;
				else if(post_cnt > 50 && post_cnt <= 52 )
					video_lead_gb 	<= 1'b1;
				else //if( post_cnt <= 42)
					control_period 	<= 1'b1;
			end
			default:;
			endcase
		end else begin
			control_period 		<= 'd0;
			island_preamble 	<= 1'b0;
			island_lead_gb 		<= 1'b0;
			data_island_period  <= 1'b0;
			island_trail_gb 	<= 1'b0;
			cnt 				<= 'd0;
			video_preamble 		<= 1'b0;
			video_lead_gb		<= 1'b0;
		end
  end
 
  always @( posedge pixelclk )
  begin
		if( post_ctlr_time )
			post_cnt <= post_cnt + 1'b1;
		else 
			post_cnt <= 'd0;
  end
 localparam DATA_PIPLINE = 2;//从4减少到2
  reg [7:0] ram_b_dat_r [DATA_PIPLINE-1:0] ;
  reg [7:0] ram_g_dat_r [DATA_PIPLINE-1:0];
  reg [7:0] ram_r_dat_r [DATA_PIPLINE-1:0];
  reg  		ram_hs_r [DATA_PIPLINE-1:0];
  reg  		ram_vs_r [DATA_PIPLINE-1:0];
  reg  		ram_de_r [DATA_PIPLINE-1:0];
  wire [9:0] ch0_dout;
  wire [9:0] ch1_dout;
  wire [9:0] ch2_dout;
  always @( posedge pixelclk )
  begin
	ram_b_dat_r[0] 	<= ram_b_dat;
	ram_g_dat_r[0] 	<= ram_g_dat;
	ram_r_dat_r[0] 	<= ram_r_dat;
	ram_hs_r[0]  	<= ram_hs;
	ram_vs_r[0] 	<= ram_vs;
	ram_de_r[0]    	<= ram_de;
  end

  generate
	genvar i;
	for( i = 0;i < DATA_PIPLINE-1 ;i = i+1)begin: dealy
	always @( posedge pixelclk )
	begin
		ram_b_dat_r[i+1] <= ram_b_dat_r[i];
		ram_g_dat_r[i+1] <= ram_g_dat_r[i];
		ram_r_dat_r[i+1] <= ram_r_dat_r[i];
		ram_hs_r[i+1]    <= ram_hs_r[i]   ;
		ram_vs_r[i+1]    <= ram_vs_r[i]   ;
		ram_de_r[i+1]    <= ram_de_r[i]   ;
	end
	end
	endgenerate


  tx_aux  tx_aux_inst (
    .clk(pixelclk),
    .rst_p(rst_p ),
    .i_hs(ram_hs ),
    .i_vs(ram_vs ),
	.video_format(video_format),
	.video_VIC(video_VIC),
    .audio_L(audio_L),
    .audio_R(audio_R),
    .audio_valid(audio_valid),
    .audio_sample_frequency(audio_samp_freq),
    .audio_word_length(audio_samp_word_len),
	.audio_N(audio_N),
	.audio_CTS(audio_CTS),
    .island_preamble(island_preamble),
    .island_lead_gb(island_lead_gb),
    .data_island_period(data_island_period),
    .island_trail_gb(island_trail_gb),
    .video_preamble(video_preamble),
    .video_lead_gb(video_lead_gb),

    .ch0_dout(ch0_dout),
    .ch1_dout(ch1_dout),
    .ch2_dout(ch2_dout)
  );
		
		

encode encb (
	.clk      			(pixelclk		),
	.rst_p      		(rst_p			),
	.din        		(ram_b_dat_r[DATA_PIPLINE-1]	),
	.aux_data           (ch0_dout		),
	.c0         		(ram_hs_r[DATA_PIPLINE-1]		),
	.c1         		(ram_vs_r[DATA_PIPLINE-1]		),
	.de         		(ram_de_r[DATA_PIPLINE-1]		),
	.dout       		(blue			)
	) ;

encode encr (
	.clk      			(pixelclk		),
	.rst_p      		(rst_p			),
	.din        		(ram_g_dat_r[DATA_PIPLINE-1]	),
	.aux_data           (ch1_dout		),
	.c0         		(1'b0			),
	.c1         		(1'b0			),
	.de         		(ram_de_r[DATA_PIPLINE-1]		),
	.dout       		(green			)
	) ;

encode encg (
	.clk      			(pixelclk		),
	.rst_p      		(rst_p			),
	.din        		(ram_r_dat_r[DATA_PIPLINE-1]	),
  	.aux_data           (ch2_dout		),
	.c0         		(1'b0			),
	.c1         		(1'b0			),
	.de         		(ram_de_r[DATA_PIPLINE-1]		),
	.dout       		(red			)
	) ;

	assign tmds_data0 = blue;
	assign tmds_data1 = green;
	assign tmds_data2 = red;
	assign tmds_clk   = 10'b1111100000;



endmodule
//Encryption end