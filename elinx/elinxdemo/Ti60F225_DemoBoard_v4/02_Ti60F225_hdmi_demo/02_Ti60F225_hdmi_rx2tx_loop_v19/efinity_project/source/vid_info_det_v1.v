

module vid_info_det #(
	parameter I_VID_WIDTH = 16,
	parameter AXI_DDR_WIDTH = 256

)(
input		wire									clk	,    
input		wire									rst_n,
input		wire									i_vs, //active hgih
input     	wire 									i_hs,
input		wire									i_de, //active high

output	reg			[23:0]							frame_cnt_o,
output	reg											frame_stable,
output	reg											negtive_sync,
output  reg  [31:0] 								ddr_frame_len,
output  reg [13:0] 									h_act,
output  reg   										h_active_error,
output  reg [13:0] 									v_act,
output  reg [13:0]  								v_total,
output  reg  										v_total_error,
output  reg [13:0] 									h_total,
output  reg  										h_total_error,
output  reg  										h_sync_error

);
localparam  VID_DATA_BYTE = I_VID_WIDTH/8;
localparam  AXI_DATA_BYTE = AXI_DDR_WIDTH/8;
  
  reg											vs_r0 = 1'b0;
  reg											de_r0 = 1'b0;
  reg											de_r1 = 1'b0;
  reg  											hs_r0 = 1'b0;
  wire 											neg_vs;
  wire											pos_vs;
  reg						[1:0]				frame_num = 'd0;  
  reg						[23:0]				frame_cnt = 'd0; 
  reg						[23:0] 				frame_len_d0 = 'd0;
  reg						[23:0] 				frame_len_d1 = 'd0; 
  reg						[23:0] 				frame_len_d2 = 'd0; 
  reg [31:0] 									total_frame_bytes = 'd0;
  reg  						[13:0] 				h_cnt = 'd0;
  reg  						[13:0] 				v_cnt = 'd0;
  reg       				[13:0] 				v_total_cnt = 'd0;
  reg   					[13:0] 				h_total_cnt = 'd0;
  reg  						[13:0] 				h_sync_len = 'd0;
  always @( posedge clk )
  begin
		if( i_de ) begin
			if( i_vs )
				negtive_sync <= 1'b1;
			else
				negtive_sync = 1'b0;
		end
  end 

  always @( posedge clk )
  begin
  		vs_r0 	<= i_vs;  		
  		de_r0 	<= i_de; 
  		de_r1 	<= de_r0;
		hs_r0 	<= i_hs;
  end
  assign neg_vs = {vs_r0,i_vs} == 2'b10;   //video start
  assign pos_vs = {vs_r0,i_vs} == 2'b01;	 //video end
  assign pos_de = {de_r0,i_de} == 2'b01;
  assign neg_de = {de_r0,i_de} == 2'b10;
  assign pos_hs = {hs_r0,i_hs} == 2'b01;
  assign neg_hs = {hs_r0,i_hs} == 2'b10;
  wire w_frame_start = (~negtive_sync & neg_vs ) || (negtive_sync & pos_vs );
  wire w_frame_end   = (~negtive_sync & pos_vs ) || (negtive_sync & neg_vs ) ;
  always @( posedge clk or negedge rst_n )
  begin
		if( ~rst_n )
			frame_cnt <= 'd0;
		else if( w_frame_start ) 
			frame_cnt <= 'd0;
		else if( de_r1 )
			frame_cnt <= frame_cnt + 1'b1;
  					
  end

  always @( posedge clk or negedge rst_n )
  begin
  		if( ~rst_n )
			frame_cnt_o <= 'd0;
		else if( w_frame_end ) 
			frame_cnt_o <= frame_cnt;
  end
reg frame_end_r0 = 'd0;
reg frame_end_r1 = 'd0;
  always @( posedge clk or negedge rst_n )
  begin
		if( !rst_n ) begin
			frame_end_r0 <= 'd0;
			frame_end_r1 <= 'd0;
		end else begin
			frame_end_r0 <= w_frame_end ;
			frame_end_r1 <= frame_end_r0;
		end
  end

  always @( posedge clk or negedge rst_n )
  begin
  		if( !rst_n ) begin
			frame_len_d0 <= 'd0; 
			frame_len_d1 <= 'd0; 
			frame_len_d2 <= 'd0; 
  		end else if( frame_end_r0 ) begin
			frame_len_d0 <= frame_end_r0;//frame_cnt;
			frame_len_d1 <= frame_len_d0;
			frame_len_d2 <= frame_len_d1;
  		end
  end

  always @( posedge clk or negedge rst_n )
  begin
  		if( !rst_n ) begin
			frame_stable <= 1'b0;
		end else if( frame_end_r1 ) begin
			if( frame_len_d0 == frame_len_d1 && frame_len_d0 == frame_len_d2 )
					frame_stable <= 1'b1;
			else
					frame_stable <= 1'b0;
		end
  end
  always @( posedge clk or negedge rst_n )
  begin
		if( !rst_n )
			total_frame_bytes = frame_cnt * VID_DATA_BYTE;
		else if(w_frame_end)
			total_frame_bytes = frame_cnt * VID_DATA_BYTE;
  end
//============================================================================================== 
// h_active calc
//==============================================================================================
  always @( posedge clk or negedge rst_n )
  begin
		if( !rst_n )
			h_cnt <= 'd0;
		else if( pos_de )
			h_cnt <= 'd0;
		else if( de_r0 )
			h_cnt <= h_cnt + 1'b1;

  end

  always @( posedge clk or negedge rst_n )
  begin
		if( !rst_n )
			h_act <= 'd0;
		else if( neg_de )
			h_act <= h_cnt ;
  end 

  always @( posedge clk or negedge rst_n )
  begin
	 if( ! rst_n )
	 	h_active_error <= 1'b0;
	 else if( neg_de && h_act != h_cnt )
		h_active_error <= 1'b1; 
	else 
		h_active_error <= 1'b0;
  end
//============================================================================================== 
//
//==============================================================================================
  always @( posedge clk or negedge rst_n )
  begin
		if( !rst_n )
			v_cnt <= 'd0;
		else if( w_frame_start )
			v_cnt <= 'd0;
		else if( pos_de )
			v_cnt <= v_cnt + 1'b1;
  end

  always @( posedge clk or negedge rst_n )
  begin
		if( !rst_n )
			v_act <= 'd0;
		else if( w_frame_start )
			v_act <= v_cnt;
  end

  always @( posedge clk or negedge rst_n )
  begin
		if( !rst_n )
			v_total_cnt <= 'd0;
		else if( w_frame_start )
			v_total_cnt <= 'd0;
		else if( pos_vs )
			v_total_cnt <= v_total_cnt + 1'b1;
  end

  always @( posedge clk or negedge rst_n )
  begin
		if( !rst_n )
			v_total <= 'd0;
		else if( w_frame_start )
			v_total <= v_total_cnt;
  end 

  always @( posedge clk )
  begin
	if( w_frame_start && v_total_cnt != v_total )
			v_total_error <= 1'b1;
	else 
			v_total_error <= 1'b0;
  end
//============================================================================================== 
//
//==============================================================================================
  always @( posedge clk or negedge rst_n )
  begin
		if( !rst_n )
			h_total_cnt <= 'd0;
		else if( pos_hs )
			h_total_cnt <= 'd0;
		else  
			h_total_cnt <= h_total_cnt + 1'b1;
  end

  always @( posedge clk or negedge rst_n )
  begin
	  	if( !rst_n )
			h_total <= 'd0;
		else if( pos_hs )
			h_total <= h_total_cnt ;
  end

  always @( posedge clk )
  begin
	 if( neg_hs )
	 		h_sync_len <= h_total_cnt ;
  end
  always @( posedge clk )
  begin
	if( neg_hs && h_total_cnt != h_sync_len )
		h_sync_error <= 1'b1;
	else 
		h_sync_error <= 1'b0;
  end


  always @( posedge clk )
  begin
	if( pos_hs && h_total_cnt != h_total )
		h_total_error <= 1'b1;
	else 
		h_total_error <= 1'b0;
  end
//====================================================================================================== 
  
  

endmodule