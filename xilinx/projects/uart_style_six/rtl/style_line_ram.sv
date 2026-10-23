// Simple dual-port RAM with no output reset. History is overwritten by the
// convolution's explicit zero-padding scan before it can be used each frame.
module style_line_ram #(
    parameter integer DATA_BITS=24,DEPTH=1926,ADDR_BITS=$clog2(DEPTH)
)(input wire clk,input wire write_enable,input wire [ADDR_BITS-1:0] write_address,
  input wire [DATA_BITS-1:0] write_data,input wire read_enable,
  input wire [ADDR_BITS-1:0] read_address,output reg [DATA_BITS-1:0] read_data);
    (* ram_style="block" *) reg [DATA_BITS-1:0] memory[0:DEPTH-1];
    always @(posedge clk) begin
        if(write_enable) memory[write_address]<=write_data;
        if(read_enable) read_data<=memory[read_address];
    end
endmodule
