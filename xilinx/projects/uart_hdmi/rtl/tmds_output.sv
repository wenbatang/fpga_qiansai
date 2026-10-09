// Encoder and 10:1 serializer are copied from the supplied HDMI RTL.
// Blue carries {VS, HS}; red and green have zero control bits.
module tmds_output(input wire pixel_clk, serial_clk, reset,
    input wire [23:0] rgb, input wire de, hsync, vsync,
    output wire tmds_clk_p, tmds_clk_n,
    output wire [2:0] tmds_data_p, tmds_data_n);
    wire [9:0] symbols [0:2];
    wire [2:0] serial;
    wire clock_serial;
    hdmi_encoder enc_b(.clkin(pixel_clk),.rstin(reset),.din(rgb[7:0]),
        .c0(hsync),.c1(vsync),.de(de),.dout(symbols[0]));
    hdmi_encoder enc_g(.clkin(pixel_clk),.rstin(reset),.din(rgb[15:8]),
        .c0(1'b0),.c1(1'b0),.de(de),.dout(symbols[1]));
    hdmi_encoder enc_r(.clkin(pixel_clk),.rstin(reset),.din(rgb[23:16]),
        .c0(1'b0),.c1(1'b0),.de(de),.dout(symbols[2]));
    genvar lane;
    generate for(lane=0;lane<3;lane=lane+1) begin: lanes
        hdmi_serializer10to1 ser(.reset(reset),.pixel_clk(pixel_clk),.pixel_clk5x(serial_clk),
            .din_parallel(symbols[lane]),.dout_serial(serial[lane]));
        OBUFDS #(.IOSTANDARD("TMDS_33")) out_buf(.I(serial[lane]),.O(tmds_data_p[lane]),.OB(tmds_data_n[lane]));
    end endgenerate
    hdmi_serializer10to1 clk_ser(.reset(reset),.pixel_clk(pixel_clk),.pixel_clk5x(serial_clk),
        .din_parallel(10'b1111100000),.dout_serial(clock_serial));
    OBUFDS #(.IOSTANDARD("TMDS_33")) clk_buf(.I(clock_serial),.O(tmds_clk_p),.OB(tmds_clk_n));
endmodule
