module hdmi_serializer10to1(
    input   logic       reset           ,
    input   logic       pixel_clk       ,
    input   logic       pixel_clk5x     ,
    input   logic [9:0] din_parallel    ,
    output  wire        dout_serial
);

wire    cascase1, cascade2  ;
OSERDESE2 #(
    .DATA_RATE_OQ("DDR"),   // DDR, SDR
    .DATA_RATE_TQ("SDR"),   // DDR, BUF, SDR
    .DATA_WIDTH(10),         // Parallel data width (2-8,10,14)
    .SERDES_MODE("MASTER"), // MASTER, SLAVE
    .TBYTE_CTL("FALSE"),    // Enable tristate byte operation (FALSE, TRUE)
    .TBYTE_SRC("FALSE"),    // Tristate byte source (FALSE, TRUE)
    .TRISTATE_WIDTH(1)      // 3-state converter width (1,4)
)
OSERDESE2_Master (
    .OFB(),             // 1-bit output: Feedback path for data
    .OQ(dout_serial),               // 1-bit output: Data path output
    .SHIFTOUT1(),
    .SHIFTOUT2(),
    .TBYTEOUT(),   // 1-bit output: Byte group tristate
    .TFB(),             // 1-bit output: 3-state control
    .TQ(),               // 1-bit output: 3-state control
    .CLK(pixel_clk5x),             // 1-bit input: High speed clock
    .CLKDIV(pixel_clk),       // 1-bit input: Divided clock
    .D1(din_parallel[0]),
    .D2(din_parallel[1]),
    .D3(din_parallel[2]),
    .D4(din_parallel[3]),
    .D5(din_parallel[4]),
    .D6(din_parallel[5]),
    .D7(din_parallel[6]),
    .D8(din_parallel[7]),
    .OCE(1'b1),             // 1-bit input: Output data clock enable
    .RST(reset),             // 1-bit input: Reset
    .SHIFTIN1(cascase1),
    .SHIFTIN2(cascade2),
    .T1(1'b0),
    .T2(1'b0),
    .T3(1'b0),
    .T4(1'b0),
    .TBYTEIN(1'b0),     // 1-bit input: Byte group tristate
    .TCE(1'b0)              // 1-bit input: 3-state clock enable
);

OSERDESE2 #(
    .DATA_RATE_OQ("DDR"),   // DDR, SDR
    .DATA_RATE_TQ("SDR"),   // DDR, BUF, SDR
    .DATA_WIDTH(10),         // Parallel data width (2-8,10,14)
    .SERDES_MODE("SLAVE"), // MASTER, SLAVE
    .TBYTE_CTL("FALSE"),    // Enable tristate byte operation (FALSE, TRUE)
    .TBYTE_SRC("FALSE"),    // Tristate byte source (FALSE, TRUE)
    .TRISTATE_WIDTH(1)      // 3-state converter width (1,4)
)
OSERDESE2_Slave (
    .OFB(),             // 1-bit output: Feedback path for data
    .OQ(),               // 1-bit output: Data path output (leave open in SLAVE)
    .SHIFTOUT1(cascase1),
    .SHIFTOUT2(cascade2),
    .TBYTEOUT(),   // 1-bit output: Byte group tristate
    .TFB(),             // 1-bit output: 3-state control
    .TQ(),               // 1-bit output: 3-state control
    .CLK(pixel_clk5x),             // 1-bit input: High speed clock
    .CLKDIV(pixel_clk),       // 1-bit input: Divided clock
    .D1(1'b0),
    .D2(1'b0),
    .D3(din_parallel[8]),
    .D4(din_parallel[9]),
    .D5(1'b0),
    .D6(1'b0),
    .D7(1'b0),
    .D8(1'b0),
    .OCE(1'b1),             // 1-bit input: Output data clock enable
    .RST(reset),             // 1-bit input: Reset
    .SHIFTIN1(),
    .SHIFTIN2(),
    .T1(1'b0),
    .T2(1'b0),
    .T3(1'b0),
    .T4(1'b0),
    .TBYTEIN(1'b0),     // 1-bit input: Byte group tristate
    .TCE(1'b0)              // 1-bit input: 3-state clock enable
);

endmodule