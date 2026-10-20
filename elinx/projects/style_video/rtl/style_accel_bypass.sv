// Stand-in for the teammate's complete RGB888-in/RGB888-out processing block.
// This copies pixels: it is neither a CNN nor proof of neural style transfer.
module style_accel_bypass(
    input wire clk,rst_n,clear,
    input wire [23:0] s_rgb,input wire s_valid,s_sof,s_eol,s_eof,
    input wire [31:0] s_frame_id,output wire s_ready,
    output wire [23:0] m_rgb,output wire m_valid,m_sof,m_eol,m_eof,
    output wire [31:0] m_frame_id,input wire m_ready
);
    reg [58:0] payload;
    reg valid;
    assign s_ready=!valid || m_ready;
    assign m_valid=valid;
    assign {m_frame_id,m_eof,m_eol,m_sof,m_rgb}=payload;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin valid<=0;payload<=0;end
        else if(clear) valid<=0;
        else if(s_ready) begin
            valid<=s_valid;
            if(s_valid) payload<={s_frame_id,s_eof,s_eol,s_sof,s_rgb};
        end
    end
endmodule
