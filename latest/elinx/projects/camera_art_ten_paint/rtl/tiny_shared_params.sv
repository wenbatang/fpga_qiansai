// Generated from frozen learned C8 exports; identical in all47 styles.
module tiny_shared_params #(parameter LAYER=1,NW=72,COUT=8)(output wire[NW*8-1:0]weights,output wire[COUT*24-1:0]biases,output wire[COUT*5-1:0]shifts);
generate
if(LAYER==1)begin
assign weights=576'he2d12a2d5ed3f2e316c6c0c3b1aaccb5b6d4fe3ecd33be2adc57d9efddeddfbcd0eddbe94ee7cc35f4cd370dc5cd070d0051eefceef4d5cfd2d9bdcfdcd3d3e628c30371fca150df;
assign biases=192'hfffe23000958fff734000a89000094ffffff00081f00000d;
assign shifts=40'h21ce6308c7;
end
else if(LAYER==3)begin
assign weights=576'hff0dfa026bfefb0afbf5d9fedeaef4f5de050a13031abafd0e0705fbe9fce462f7fae7febe2843949278c02d672042114e68260e2a0416db0cc777cd1cc91905fbfdf28d01fcff06;
assign biases=192'hfffb510007f4fffe88000a26000469ffe64400002f000f41;
assign shifts=40'h298a741ca6;
end
else if(LAYER==5)begin
assign weights=576'h58303c231d40da115fa2ff42d4958e04709fcf6faf664f6fcfbfcfe03feff4f060006fc151bfe58f1470a511c01f4fef874f202f3fc08e3feee43eb03e3fcfffcfff657f5fef0fb;
assign biases=192'h605fffe3bcfff766ffe9d3ff81b7fffdf7000b8afffa5f;
assign shifts=40'h4a0c7494c6;
end
else if(LAYER==7)begin
assign weights=576'h70c0910a30e041802322c1a6de9411d4e3ffaf6faf575fafdf7fafbf8f7f649f7fcf5fa01fae7f066f7fcf3eb151afd22fa2c0646f0fcfffdfc72fbfefefde0035b2e83ea01f35f;
assign biases=192'hfff297ff855cfff843000602fffbf8ffea02fff94bffeb5d;
assign shifts=40'h3a4e62a0e6;
end
else if(LAYER==9)begin
assign weights=192'h262b17fcb13006014d4554dbffe51ec648efd09e41f57424;
assign biases=72'hfff9f2ffe5ebffe46e;
assign shifts=15'h18e7;
end
else begin assign weights=0;assign biases=0;assign shifts=0;end
endgenerate
endmodule
