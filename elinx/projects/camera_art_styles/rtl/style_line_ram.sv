// Simple dual-port RAM with no output reset. History is overwritten by the
// convolution's explicit zero-padding scan before it can be used each frame.
module style_line_ram #(
    parameter integer DATA_BITS=24,DEPTH=1926,ADDR_BITS=$clog2(DEPTH)
)(input wire clk,input wire write_enable,input wire [ADDR_BITS-1:0] write_address,
  input wire [DATA_BITS-1:0] write_data,input wire read_enable,
  input wire [ADDR_BITS-1:0] read_address,output wire [DATA_BITS-1:0] read_data);
 generate if(DEPTH>2048)begin:split
    // Two <=2048-deep banks use RAM10's wider data mode. Both retain the
    // original one-clock read latency and read-enable hold behavior.
    localparam HALF=(DEPTH+1)/2,LOCAL_BITS=$clog2(HALF);
    (* ram_style="block" *) reg[DATA_BITS-1:0]lo[0:HALF-1],hi[0:DEPTH-HALF-1];
    reg[DATA_BITS-1:0]a,b;reg selected;
    wire wh=write_address>=HALF,rh=read_address>=HALF;
    wire[LOCAL_BITS-1:0]wa=wh?write_address-HALF:write_address;
    wire[LOCAL_BITS-1:0]ra=rh?read_address-HALF:read_address;
    always @(posedge clk)begin
     if(write_enable)begin if(wh)hi[wa]<=write_data;else lo[wa]<=write_data;end
     if(read_enable)begin selected<=rh;if(rh)b<=hi[ra];else a<=lo[ra];end
    end
    assign read_data=selected?b:a;
 end else begin:single
    reg[DATA_BITS-1:0]q;
    (* ram_style="block" *) reg [DATA_BITS-1:0] memory[0:DEPTH-1];
    always @(posedge clk) begin
        if(write_enable) memory[write_address]<=write_data;
        if(read_enable) q<=memory[read_address];
    end
    assign read_data=q;
 end endgenerate
endmodule
