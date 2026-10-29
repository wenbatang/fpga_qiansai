// Experimental sequentially loaded shallow weights. Each word must be written
// exactly once in ascending order before inference. There is deliberately no
// reset: a complete model load replaces every bit, including the final short
// bank. This retains the established 365-transaction parameter protocol.
module fps_srl_weights #(
 parameter integer DATA_BITS=288,WORDS=36,ADDR_BITS=$clog2(WORDS)
)(input wire clk,write_enable,input wire[ADDR_BITS-1:0]write_address,
 input wire[DATA_BITS-1:0]write_data,input wire[ADDR_BITS-1:0]read_address,
 output wire[DATA_BITS-1:0]read_data);
 localparam BANKS=(WORDS+7)/8,SEL_BITS=BANKS>1?$clog2(BANKS):1;
 wire[SEL_BITS-1:0]write_bank=write_address>>3,read_bank=read_address>>3;
 wire[2:0]position=read_address;
 wire[DATA_BITS-1:0]bank_data[0:BANKS-1];
 genvar b,k;
 generate for(b=0;b<BANKS;b=b+1)begin:bank
  localparam N=WORDS-b*8>8?8:WORDS-b*8;
  for(k=0;k<DATA_BITS;k=k+1)begin:bit_store
   (* syn_srlstyle="srl" *)reg[N-1:0]shift_reg;
   if(N==1)begin:one
    always @(posedge clk)if(write_enable && write_bank==b)shift_reg<=write_data[k];
   end else begin:many
    always @(posedge clk)if(write_enable && write_bank==b)shift_reg<={shift_reg[N-2:0],write_data[k]};
   end
   assign bank_data[b][k]=shift_reg[N-1-position];
  end
 end endgenerate
 assign read_data=bank_data[read_bank];
endmodule
