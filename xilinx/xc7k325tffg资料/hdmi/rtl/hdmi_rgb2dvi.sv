module hdmi_rgb2dvi(
    input   logic           pixel_clk   ,
    input   logic           pixel_clk5x ,
    input   logic           rst_n       ,
    input   logic           pixel_den   ,
    input   logic [23:0]    pixel_rgb   ,
    output  logic           hdmi_hsync  ,
    output  logic           hdmi_vsync  ,

    output  logic           tmds_clk_p  ,
    output  logic           tmds_clk_n  ,
    output  logic [2:0]     tmds_data_p ,
    output  logic [2:0]     tmds_data_n ,

    output  logic           tmds_out_en
);

wire            reset       ;
wire    [9:0]   red_10bit   ;
wire    [9:0]   green_10bit ;
wire    [9:0]   blue_10bit  ;

wire    [2:0]   tmds_data_serial    ;
wire            tmds_clk_serial     ;

assign  tmds_out_en = 1'b1              ;

//异步复位同步释放
hdmi_reset_syn u_hdmi_reset_syn(
    .reset_n   	(rst_n      ),
    .clk       	(pixel_clk  ),
    .syn_reset 	(reset      )
);


hdmi_encoder
encoder_r(
    .clkin 	(pixel_clk  ),
    .rstin 	(reset  ),
    .din   	(pixel_rgb[23:16]    ),
    .c0    	(hdmi_hsync     ),
    .c1    	(hdmi_vsync     ),
    .de    	(pixel_den     ),
    .dout  	(red_10bit   )
);


hdmi_encoder
encoder_g(
    .clkin 	(pixel_clk  ),
    .rstin 	(reset  ),
    .din   	(pixel_rgb[15:8]    ),
    .c0    	(1'b0     ),
    .c1    	(1'b0     ),
    .de    	(pixel_den     ),
    .dout  	(green_10bit   )
);


hdmi_encoder
encoder_b(
    .clkin 	(pixel_clk  ),
    .rstin 	(reset  ),
    .din   	(pixel_rgb[7:0]    ),
    .c0    	(1'b0     ),
    .c1    	(1'b0     ),
    .de    	(pixel_den  ),
    .dout  	(blue_10bit   )
);


hdmi_serializer10to1 u_hdmi_serializer10to1_r(
    .reset        	(reset         ),
    .pixel_clk    	(pixel_clk     ),
    .pixel_clk5x  	(pixel_clk5x   ),
    .din_parallel 	(red_10bit  ),
    .dout_serial  	(tmds_data_serial[2]   )
);

hdmi_serializer10to1 u_hdmi_serializer10to1_g(
    .reset        	(reset         ),
    .pixel_clk    	(pixel_clk     ),
    .pixel_clk5x  	(pixel_clk5x   ),
    .din_parallel 	(green_10bit  ),
    .dout_serial  	(tmds_data_serial[1]   )
);

hdmi_serializer10to1 u_hdmi_serializer10to1_b(
    .reset        	(reset         ),
    .pixel_clk    	(pixel_clk     ),
    .pixel_clk5x  	(pixel_clk5x   ),
    .din_parallel 	(blue_10bit  ),
    .dout_serial  	(tmds_data_serial[0]   )
);

hdmi_serializer10to1 u_hdmi_serializer10to1_clk(
    .reset        	(reset         ),
    .pixel_clk    	(pixel_clk     ),
    .pixel_clk5x  	(pixel_clk5x   ),
    .din_parallel 	(10'b1111100000  ),
    .dout_serial  	(tmds_clk_serial   )
);

OBUFDS #(
    .IOSTANDARD("TMDS_33") // Specify the output I/O standard
) tmds0 (
    .O(tmds_data_p[0]),     // Diff_p output (connect directly to top-level port)
    .OB(tmds_data_n[0]),   // Diff_n output (connect directly to top-level port)
    .I(tmds_data_serial[0])      // Buffer input 
);

OBUFDS #(
    .IOSTANDARD("TMDS_33") // Specify the output I/O standard
) tmds1 (
    .O(tmds_data_p[1]),     // Diff_p output (connect directly to top-level port)
    .OB(tmds_data_n[1]),   // Diff_n output (connect directly to top-level port)
    .I(tmds_data_serial[1])      // Buffer input 
);

OBUFDS #(
    .IOSTANDARD("TMDS_33") // Specify the output I/O standard
) tmds2 (
    .O(tmds_data_p[2]),     // Diff_p output (connect directly to top-level port)
    .OB(tmds_data_n[2]),   // Diff_n output (connect directly to top-level port)
    .I(tmds_data_serial[2])      // Buffer input 
);

OBUFDS #(
    .IOSTANDARD("TMDS_33") // Specify the output I/O standard
) tmdsclk (
    .O(tmds_clk_p),     // Diff_p output (connect directly to top-level port)
    .OB(tmds_clk_n),   // Diff_n output (connect directly to top-level port)
    .I(tmds_clk_serial)      // Buffer input 
);

endmodule