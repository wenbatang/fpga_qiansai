// One runtime model set; constant byte/channel writers avoid dynamic partial writes.
module full_parameter_bank #(parameter LAYER=0,NW=18,COUT=6)(
 input wire clk,cfg_valid,input wire[15:0]cfg_address,input wire[31:0]cfg_data,
 output wire[NW*8-1:0]weights,output wire[COUT*24-1:0]biases,output wire[COUT*5-1:0]shifts);
 genvar w,c;
 generate for(w=0;w<NW;w=w+1)begin:weight_writer
  reg[7:0]value;
  always @(posedge clk)if(cfg_valid && cfg_address[15:12]==LAYER && cfg_address[11:10]==0 && cfg_address[9:2]==w/4)value<=cfg_data[(w%4)*8+:8];
  assign weights[w*8+:8]=value;
 end
 for(c=0;c<COUT;c=c+1)begin:channel_writer
  // All frozen models prove abs(bias)+255*sum(abs(weight)) <2**21.
  // Config retains32 bits; sign extension preserves the original interface.
  reg signed[21:0]bias;reg[4:0]shift;
  always @(posedge clk)if(cfg_valid && cfg_address[15:12]==LAYER && cfg_address[9:0]==c)begin
   if(cfg_address[11:10]==1)bias<=cfg_data[21:0];
   if(cfg_address[11:10]==2)shift<=cfg_data[4:0];
  end
  assign biases[c*24+:24]={{2{bias[21]}},bias};assign shifts[c*5+:5]=shift;
 end endgenerate
endmodule
