// Experimental history store. Banks are at most 1024 words deep, avoiding
// wide features mapped onto 8K/16K-deep narrow RAM configurations. The read
// remains one clock, read-enable holds data, and no memory clear is added.
module fps_line_ram #(
 parameter integer DATA_BITS=48,DEPTH=11424,ADDR_BITS=$clog2(DEPTH)
)(input wire clk,write_enable,input wire[ADDR_BITS-1:0]write_address,
 input wire[DATA_BITS-1:0]write_data,input wire read_enable,
 input wire[ADDR_BITS-1:0]read_address,output wire[DATA_BITS-1:0]read_data);
 localparam BANKS=(DEPTH+1023)/1024,SEL_BITS=BANKS>1?$clog2(BANKS):1;
 wire[SEL_BITS-1:0]write_bank=write_address>>10,read_bank=read_address>>10;
 wire[9:0]write_local=write_address,read_local=read_address;
 wire[DATA_BITS-1:0]bank_data[0:BANKS-1];reg[SEL_BITS-1:0]selected;
 always @(posedge clk)if(read_enable)selected<=read_bank;
 genvar b;
 generate for(b=0;b<BANKS;b=b+1)begin:bank
  localparam N=DEPTH-b*1024>1024?1024:DEPTH-b*1024;
  (* ram_style="block" *)reg[DATA_BITS-1:0]memory[0:N-1];
  reg[DATA_BITS-1:0]q;
  always @(posedge clk)begin
   if(write_enable && write_bank==b)memory[write_local]<=write_data;
   if(read_enable && read_bank==b)q<=memory[read_local];
  end
  assign bank_data[b]=q;
 end endgenerate
 assign read_data=bank_data[selected];
endmodule
