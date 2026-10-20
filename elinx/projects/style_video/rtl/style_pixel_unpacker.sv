module style_pixel_unpacker(
    input wire clk,rst_n,clear,
    input wire [127:0] s_data,input wire s_valid,s_last,output wire s_ready,
    output wire [23:0] m_rgb,output wire m_valid,m_last,input wire m_ready
);
    reg [127:0] data;
    reg valid,last;
    reg [1:0] lane;
    assign m_valid=valid; assign m_rgb=data[lane*32+:24];
    assign m_last=last && lane==3;
    assign s_ready=!valid || (m_ready && lane==3);
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin valid<=0;last<=0;lane<=0;data<=0;end
        else if(clear) begin valid<=0;last<=0;lane<=0;end
        else begin
            if(valid && m_ready) begin
                if(lane==3) begin valid<=0;lane<=0;end else lane<=lane+1'b1;
            end
            if(s_valid && s_ready) begin data<=s_data;last<=s_last;valid<=1;lane<=0;end
        end
    end
endmodule
