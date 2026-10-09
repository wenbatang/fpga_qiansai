// 100 MHz MIG UI reference -> VCO 742.5 MHz -> 74.25 / 371.25 MHz.
// Cascade from the MIG UI clock; exact 720p rates, not 75/375 MHz.
module video_clocks(input wire reference_100mhz, reset,
                    output wire pixel_clk, serial_clk, locked);
    wire feedback, feedback_buffered, pixel_raw, serial_raw;
    MMCME2_BASE #(
        .BANDWIDTH("OPTIMIZED"), .CLKIN1_PERIOD(10.0),
        .DIVCLK_DIVIDE(5), .CLKFBOUT_MULT_F(37.125),
        .CLKOUT0_DIVIDE_F(10.0), .CLKOUT1_DIVIDE(2),
        .STARTUP_WAIT("FALSE")
    ) mmcm (
        .CLKIN1(reference_100mhz), .RST(reset), .PWRDWN(1'b0),
        .CLKFBIN(feedback_buffered), .CLKFBOUT(feedback), .CLKFBOUTB(),
        .CLKOUT0(pixel_raw), .CLKOUT0B(), .CLKOUT1(serial_raw), .CLKOUT1B(),
        .CLKOUT2(), .CLKOUT2B(), .CLKOUT3(), .CLKOUT3B(),
        .CLKOUT4(), .CLKOUT5(), .CLKOUT6(), .LOCKED(locked)
    );
    BUFG fb_buf(.I(feedback),.O(feedback_buffered));
    BUFG pix_buf(.I(pixel_raw),.O(pixel_clk));
    BUFG ser_buf(.I(serial_raw),.O(serial_clk));
endmodule
