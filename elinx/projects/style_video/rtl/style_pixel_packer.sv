// DDR layout: one pixel occupies a little-endian word 0x00RRGGBB.
// Four consecutive pixels become one 128-bit AXI beat, earliest in bits31:0.
module style_pixel_packer(
    input wire clk,rst_n,clear,
    input wire [23:0] s_rgb, input wire s_valid,s_last, output wire s_ready,
    output wire [127:0] m_data, output wire m_valid,m_last,input wire m_ready
);
    reg [127:0] pack_data,out_data;
    reg [1:0] lane;
    reg valid,last;
    assign s_ready = !valid || m_ready;
    assign m_data=out_data; assign m_valid=valid; assign m_last=last;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin lane<=0; valid<=0; last<=0; pack_data<=0; out_data<=0; end
        else if(clear) begin lane<=0; valid<=0; last<=0; pack_data<=0; end
        else begin
            if(valid && m_ready) valid<=0;
            if(s_valid && s_ready) begin
                pack_data[lane*32+:32]<={8'h00,s_rgb};
                if(lane==3 || s_last) begin
                    case(lane)
                        0:out_data<={96'b0,8'b0,s_rgb};
                        1:out_data<={64'b0,8'b0,s_rgb,pack_data[31:0]};
                        2:out_data<={32'b0,8'b0,s_rgb,pack_data[63:0]};
                        3:out_data<={8'b0,s_rgb,pack_data[95:0]};
                    endcase
                    valid<=1;last<=s_last;lane<=0;pack_data<=0;
                end else lane<=lane+1'b1;
            end
        end
    end
endmodule
