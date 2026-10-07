

module frame_bitslip (
    input                   clk     ,
    input                   rstn    ,
    input                   bitslip ,
    input           [7:0]   data_in ,
    output reg      [7:0]   data_out
);

    reg     [15:0]  data_buff;
    reg             bitslip_dly1, bitslip_dly2;
    reg     [2:0]   Output_switch;
    wire            pos_bitslip;

always @(posedge clk or negedge rstn) begin
    if (!rstn) begin
        bitslip_dly1 <= 1'b0;
        bitslip_dly2 <= 1'b0;
    end else begin
        bitslip_dly1 <= bitslip;
        bitslip_dly2 <= bitslip_dly1;
    end
end
assign pos_bitslip = {bitslip_dly2,bitslip_dly1} == 2'b01;
//Output_switch
always @(posedge clk or negedge rstn) begin
    if (!rstn) begin
        Output_switch <= 3'b0;
    end else begin
        if(pos_bitslip) begin
            Output_switch <= Output_switch + 1;
        end else begin
            Output_switch <= Output_switch;
        end
    end
end

always @(posedge clk or negedge rstn) begin
    if (!rstn) begin
        data_buff <= 16'h0000;
    end else begin
        data_buff <= {data_in, data_buff[15:8]};
    end
end

always @(posedge clk or negedge rstn) begin
    if (!rstn) begin
        data_out <= 8'h00;
    end else begin
        case(Output_switch)
            3'h0: data_out <= data_buff[15:8];
            3'h1: data_out <= data_buff[14:7];
            3'h2: data_out <= data_buff[13:6];
            3'h3: data_out <= data_buff[12:5];
            3'h4: data_out <= data_buff[11:4];
            3'h5: data_out <= data_buff[10:3];
            3'h6: data_out <= data_buff[ 9:2];
            3'h7: data_out <= data_buff[ 8:1];
        endcase
    end
end
endmodule