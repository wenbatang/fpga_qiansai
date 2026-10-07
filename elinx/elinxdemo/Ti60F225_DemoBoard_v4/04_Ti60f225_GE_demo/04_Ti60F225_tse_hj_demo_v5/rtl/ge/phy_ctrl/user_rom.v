module user_rom #(

    parameter ROM_SIZE                     = 17,   
    parameter TOTAL_ROM_DEPTH              = 64, // 6*7
    parameter ADDR_WIDTH                   = 6   // alt_clogb2(42) 
) (
    input  wire                  clock,
    input  wire [ADDR_WIDTH-1:0] addr_ptr,
    output wire [ROM_SIZE-1:0]   rdata_out
);

reg  [ROM_SIZE-1:0]   ROM [0:TOTAL_ROM_DEPTH-1];
wire [ROM_SIZE-1:0]   DATAA = {ROM_SIZE{1'b0}};
wire [ADDR_WIDTH-1:0] RADDR;
   
initial begin
		//9293		ADDR = 0X64		//phy_addr /data/read_en[1]
    ROM[0]  <= {16'h4140,1'b1}; //
    ROM[1]  <= {16'h0000,1'b1}; //
    ROM[2]  <= {16'h0000,1'b1}; //
    ROM[3]  <= {16'h0000,1'b1}; //    
    ROM[4]  <= {16'h0000,1'b1};
    ROM[5]  <= {16'h0000,1'b1};
    ROM[6]  <= {16'h0000,1'b1};
    ROM[7]  <= {16'h0000,1'b1};//05
    ROM[8]  <= {16'h0000,1'b1};
    ROM[9]  <= {16'h0000,1'b1};//
    ROM[10] <= {16'h0000,1'b1};
    ROM[11] <= {16'h0000,1'b1};//
    ROM[12] <= {16'h0000,1'b1};//05
    ROM[13] <= {16'h0000,1'b1};//hpd pull high
    ROM[14] <= {16'h0000,1'b1};
    ROM[15] <= {16'h0000,1'b1};
    ROM[16] <= {16'h0000,1'b1};
   	ROM[17] <= {16'h0000,1'b1};
   	ROM[18] <= {16'h0000,1'b1};
    ROM[19] <= {16'h0000,1'b1};
    ROM[20] <= {16'h0000,1'b1};
    ROM[21] <= {16'h0000,1'b1};
    ROM[22] <= {16'h0000,1'b1};
    ROM[23] <= {16'h0000,1'b1};
    ROM[24] <= {16'h0000,1'b1};
    ROM[25] <= {16'h0000,1'b1};
    ROM[26] <= {16'h0000,1'b1};
    ROM[27] <= {16'h0000,1'b1};
    ROM[28] <= {16'h0000,1'b1};
    ROM[29] <= {16'h0000,1'b1};
    ROM[30] <= {16'h0000,1'b1};
    ROM[31] <= {16'h0000,1'b1};
    ROM[32] <= {16'h4140,1'b1};//0
    ROM[33] <= {16'h0000,1'b1};//1
    ROM[34] <= {16'h0000,1'b1};//2
    ROM[35] <= {16'h0000,1'b1};//3
    ROM[36] <= {16'h81e1,1'b1};//4
    ROM[37] <= {16'h0000,1'b1};//5
    ROM[38] <= {16'h0000,1'b1};//6
    ROM[39] <= {16'h0000,1'b1};//7
    ROM[40] <= {16'h0000,1'b1};//8
    ROM[41] <= {16'h0000,1'b1};//9
    ROM[42] <= {16'h0000,1'b1};//10
    ROM[43] <= {16'h0000,1'b1};//11
    ROM[44] <= {16'h0000,1'b1};//12
    ROM[45] <= {16'h0000,1'b1};//13
    ROM[46] <= {16'h0000,1'b1};//14
    ROM[47] <= {16'h0000,1'b1};//15
    ROM[48] <= {16'h0000,1'b1};//16  
    ROM[49] <= {16'h1111,1'b1};// 
    ROM[50] <= {16'habcd,1'b1};// 
    ROM[51] <= {16'h1234,1'b1};//   
    ROM[52] <= {16'h4678,1'b1};//
    ROM[53] <= {16'h4321,1'b1};// 
    ROM[54] <= {16'haaaa,1'b1};//
    ROM[55] <= {16'hbbbb,1'b1};//
    ROM[56] <= {16'hcccc,1'b1};//
    ROM[57] <= {16'hdddd,1'b1};//
    ROM[58] <= {16'heeee,1'b1};//
    ROM[59] <= {16'hffff,1'b1};//
    ROM[60] <= {16'h2222,1'b1};//   
    ROM[61] <= {16'h3333,1'b1};//
    ROM[62] <= {16'h4444,1'b0};//
    ROM[63] <= {16'h0000,1'b0};//
      
end 

// write is unused
wire [ADDR_WIDTH-1:0] ADDRA = {ADDR_WIDTH{1'b0}}; 
wire                  WEA   = 1'b0; 
always @ (posedge clock)
begin
    if (WEA) begin
        ROM[ADDRA] <= DATAA;
    end
end
   
assign RADDR = addr_ptr;
   
reg [ROM_SIZE-1:0] RDATA;
always @ (posedge clock)
begin
     RDATA <= ROM[RADDR];
end

assign rdata_out = RDATA;
   
endmodule			      