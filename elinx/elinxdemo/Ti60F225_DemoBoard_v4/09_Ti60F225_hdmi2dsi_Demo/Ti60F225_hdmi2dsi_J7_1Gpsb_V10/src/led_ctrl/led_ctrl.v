module led_ctrl #(
    parameter LED_NUM = 4,
    parameter LED_TIME = 1000

)(
input wire  clk,
input wire  rst_n,
input wire  [LED_NUM-1:0] en,

output reg [LED_NUM-1:0] led = 'd0
);
//===================================================================== 
//localparam
//=====================================================================
localparam CNT_WIDTH = log2(LED_TIME);
//===================================================================== 
//reg
//=====================================================================
reg [CNT_WIDTH-1:0] cnt = 'd0;
reg [LED_NUM-1:0] en_r = 'd0;
reg                 cnt_end = 'd0;
//===================================================================== 
//main code
//=====================================================================
always @( posedge clk or negedge rst_n )
begin
    if( !rst_n ) begin
        cnt <= 'd0;
        cnt_end <= 1'b0;
    end else if( |en) begin
        cnt_end <= 1'b0;
        if( cnt == LED_TIME-1 ) begin
            cnt <= 'd0;
            cnt_end <= 1'b1;
        end else 
            cnt <= cnt + 1'b1;
    end


end 

always @( posedge clk or negedge rst_n )
begin
    if( !rst_n )
        en_r <= 'd0;
    else 
        en_r <= en; 
end

generate
genvar i;
for( i = 0;i < LED_NUM ;i = i+1)begin: led_al
always @( posedge clk )
begin
    if( en_r[i])
        led[i] <= cnt_end ? ~led[i] : led[i];
    else 
        led[i] <= 'd0;
end
end
endgenerate

function integer log2;
	input	integer	val;
	integer	i;
	begin
		log2 = 0;
		for (i=0; 2**i<val; i=i+1)
			log2 = i+1;
	end
endfunction

endmodule