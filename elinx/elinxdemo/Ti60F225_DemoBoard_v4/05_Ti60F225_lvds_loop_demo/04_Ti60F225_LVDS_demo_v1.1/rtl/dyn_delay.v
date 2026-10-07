
module dyn_delay(
input					clk,
input 				rst_n,
input	 				dyn_en,
input		[5:0] dly_d,
input				  dly_inc,


output		dyn_rst,
output	reg	dyn_inc,
output	reg	dyn_ena,
output	reg	cal_busy

);

wire dyn_en_pulse ;
reg [5:0] dly_d_r;
reg [5:0] dly_d_r0;
reg 	dly_inc_r;
reg	dyn_en_r0 = 1'b0;
reg	dyn_en_r1 = 1'b0;
always @( posedge clk or negedge rst_n )
begin
		if( !rst_n ) begin
				dyn_en_r0 <= 1'b0;
				dyn_en_r1 <= 1'b0;
		end else begin
				dyn_en_r0 <= dyn_en ;
				dyn_en_r1 <= dyn_en_r0;
		end
			
end

always @( posedge clk or negedge rst_n )
begin
		if( !rst_n ) 
				dly_d_r0 <= 'd0;
		else
				dly_d_r0 <= dly_d;
end



assign dyn_en_pulse = {dyn_en_r1,dyn_en_r0} == 2'b01;
               
assign dyn_rst = dyn_en_pulse;
always @( posedge clk or negedge rst_n )
begin
		if( !rst_n ) begin        			
				dly_d_r <= 0;     
		end else if(dyn_en_pulse ) begin	
				dly_d_r <= dly_d_r0; 
		end else begin											
				dly_d_r <= dly_d_r - |dly_d_r;  	
		end
end        

always @( posedge clk or negedge rst_n )
begin
		if( !rst_n ) begin        			
				dly_inc_r <= 0;     
		end else if(dyn_en_pulse ) begin	
				dly_inc_r <= dly_inc; 
		end
end     

always @( posedge clk or negedge rst_n )
begin
		if( !rst_n ) 
				dyn_ena <= 1'b0;
		else
				dyn_ena <= |dly_d_r ;
end

always @( posedge clk )
begin
		dyn_inc <= dly_inc_r	;  
end

always @( posedge clk )
begin
	cal_busy <= dyn_en || (|dly_d_r) || dyn_en_pulse || (|{dyn_en_r1,dyn_en_r0});
end



endmodule      
     
