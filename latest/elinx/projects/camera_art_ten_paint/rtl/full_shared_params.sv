// Frozen shared DW/head from trained full-resolution C6 exports.
module full_shared_params #(parameter LAYER=1,NW=54,COUT=6)(output wire[NW*8-1:0]weights,output wire[COUT*24-1:0]biases,output wire[COUT*5-1:0]shifts);
generate
if(LAYER==1)begin
assign weights=432'h290124febe10f31ef6e81db83ef321e313bd5c403c496c0f36391f4b38cff4bb11e79da0ecd6fde53e16af0b081a1d5eeafe32fa1a3c;assign biases=144'hffe9a1000cc4fff1c8000fa2000430fff8c6;assign shifts=30'he739cc6;end
else if(LAYER==3)begin
assign weights=432'h69cff0bc0a4fe0324afe91ecb2545a2011ac40bfee0fb0ea0d6a7f58df3bbb38bf8b51cf93ee92478fc0f1bcbf7bde9c4d8c9decddd;assign biases=144'h13ac0009df001237005de6ffeb89000da7;assign shifts=30'he73a0e6;end
else if(LAYER==5)begin
assign weights=432'hd401239d11f142317ecfa85c52813b1f0e419c63eda82bb2bcb2e0d0afbeda2e80dc90050b1d708c06f35fa3484c715d2f50825b82f;assign biases=144'hffe1af004897004e26001c5dffcc76003d07;assign shifts=30'h10849ce8;end
else if(LAYER==7)begin
assign weights=432'h2ece49aaa3c5dffc5cd8313c4f7b2ff2454607f019f1a60838001e49facfe02c051e04c743b928de0ee50cd23813fd0df1b80214fe06;assign biases=144'h8e56ff98a5ffed23fffa09fffe150002e4;assign shifts=30'h149414c5;end
else if(LAYER==9)begin
assign weights=144'h70a413d53e14521722f8c40f63233ff6a7b9;assign biases=72'hfff39cffee2d0000c9;assign shifts=15'h1ce7;end
else begin assign weights=0;assign biases=0;assign shifts=0;end
endgenerate
endmodule
