module carry_chain
#(
parameter TAP = 128
)
(
input            clk          ,
input            carry_in     ,
output [TAP-1:0] carry_tap 
);

localparam LEVEL = TAP + 2;

wire [LEVEL-2:0] carry_chain;
wire [LEVEL-2:0] carry_tap_i;
reg [TAP-1:0] carry_tap_reg;

generate
genvar i;
     for (i=0;i<LEVEL-1;i=i+1) begin : CHAIN_GEN          
          if (i==0) begin
               EFX_ADD#
               (
               .I0_POLARITY(1'b1),
               .I1_POLARITY(1'b1) 
               )
               EFX_ADD_inst
               (
               .O (carry_tap_i[i]  ),
               .CO(carry_chain[i]  ),
               .I0(carry_in        ),
               .I1(1'b1            ),
               .CI(1'b0            )    
               );
          end          
          else begin          
               EFX_ADD#
               (
               .I0_POLARITY(1'b1),
               .I1_POLARITY(1'b1) 
               )
               EFX_ADD_inst
               (
               .O (carry_tap_i[i]  ),
               .CO(carry_chain[i]  ),
               .I0(1'b0            ),
               .I1(1'b1            ),
               .CI(carry_chain[i-1])       
               );
          end                   
     end
endgenerate

always @ (posedge clk ) begin
     carry_tap_reg <= ~carry_tap_i[LEVEL-2:1];
end

assign carry_tap = carry_tap_reg;   
  
endmodule