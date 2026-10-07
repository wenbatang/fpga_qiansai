module buffer
#(
	parameter	DW		= 16,
	parameter	DEPTH	= 1
)
(
	input	[DW-1:0]i_d,
	output	[DW-1:0]o_d
);

wire	[DW-1:0]w_I[0:DEPTH];

assign	w_I[0]	= i_d;

genvar i, j;
generate
	for (j=0; j<DEPTH; j=j+1)
	begin
		for (i=0; i<DW; i=i+1)
		begin
			EFX_LUT4
			#(
				.LUTMASK(16'h2222)
			)
			inst_EFX_LUT4
			(
				.I0(w_I[j][i]),
				.I1(1'b0),
				.O(w_I[j+1][i])
			);
		end
	end
endgenerate

assign	o_d	= w_I[DEPTH];

endmodule
