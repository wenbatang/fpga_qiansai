
module pixcel_122 #(
    parameter DIN = 16,
    parameter PAR_WIDTH  = 4
)(
    input wrclk,
    input rdclk,
    input rst_n,
    input [DIN-1:0] din,
    input i_hs,
    input i_vs,
    input i_de,

    output reg [DIN*PAR_WIDTH-1:0] dout,
    output reg o_hs,
    output reg o_vs,
    output reg o_de
);
parameter     AW_C          = $clog2(16)  ;
parameter     PAR_WID       = $clog2(PAR_WIDTH)  ;
localparam   INER_DIN = DIN + 3;
reg                 de_r0 = 'd0;
reg                 hs_r0 = 'd0;
reg                 vs_r0 = 'd0;
reg                 fifo_rd_en = 'd0;
reg  [DIN-1:0]          din_r0 = 'd0;
reg  [INER_DIN*2-1:0]    fifo_wr_data;
wire [INER_DIN*2-1:0] fifo_rd_data;
reg  [PAR_WID-1:0]  width_sel;
reg                 din_valid;
always@( posedge wrclk )
begin
    de_r0 <= i_de;
    din_r0 <= din;
    hs_r0 <= i_hs;
    vs_r0 <= i_vs;
end
wire pos_de = {de_r0,i_de} == 2'b01;
always @( posedge wrclk or negedge rst_n )
begin
    if( !rst_n )
        width_sel <= 'd0;
    else if( pos_de )
        width_sel <= 'd0;
    else if( PAR_WIDTH-1 == width_sel )
        width_sel <= 'd0;
    else
        width_sel <= width_sel + 1'b1;
end




generate
    if (PAR_WIDTH == 2) begin : new_data_a_generation
        always @( posedge wrclk )
        begin
            case( width_sel )
            0: fifo_wr_data[INER_DIN-1:0] <= {hs_r0,vs_r0,de_r0,din_r0};
            1: fifo_wr_data[INER_DIN*2-1:INER_DIN] <= {hs_r0,vs_r0,de_r0,din_r0};
            default :;
            endcase
                 
        end

        always @( posedge wrclk )
        begin
            if( !rst_n ) din_valid <= 1'b0;
            else if( width_sel == 1 ) din_valid <= 1'b1;
            else din_valid <= 1'b0;

        end
    end else begin
        always @( posedge wrclk )
        begin
            case( width_sel )
            0: fifo_wr_data[INER_DIN-1:0] <= {hs_r0,vs_r0,de_r0,din_r0};
            1: fifo_wr_data[INER_DIN*2-1:INER_DIN] <= {hs_r0,vs_r0,de_r0,din_r0};
            2: fifo_wr_data[INER_DIN*3-1:INER_DIN*2] <= {hs_r0,vs_r0,de_r0,din_r0};
            3: fifo_wr_data[INER_DIN*4-1:INER_DIN*3] <= {hs_r0,vs_r0,de_r0,din_r0};
            default :;
            endcase
                 
        end

        always @( posedge wrclk )
        begin
            if( !rst_n ) din_valid <= 1'b0;
            else if( width_sel == 3 ) din_valid <= 1'b1;
            else din_valid <= 1'b0;

        end
    end
    endgenerate




wire [AW_C-1:0] RdDNum ;

DC_FIFO # (
    .FIFO_MODE("Normal"),
    .DATA_WIDTH(INER_DIN*2),
    .FIFO_DEPTH(16)
  )
  DC_FIFO_inst (
    .Reset(~rst_n),
    .WrClk(wrclk),
    .WrEn(din_valid),
    .WrDNum(),
    .WrFull(),
    .WrData(fifo_wr_data),
    .RdClk(rdclk),
    .RdEn(fifo_rd_en),
    .RdDNum(RdDNum),
    .RdEmpty(),
    .DataVal(fifo_rd_valid),
    .RdData(fifo_rd_data)
  );

  always @( posedge rdclk or negedge rst_n )
  begin
        if( !rst_n )
            fifo_rd_en <= 1'b0;
        else if( RdDNum >= 8 )
            fifo_rd_en <= 1'b1;
  end

  always @( posedge rdclk  )
  begin
         dout <= {fifo_rd_data[DIN+INER_DIN+2:INER_DIN],fifo_rd_data[DIN-1:0]};
         o_de <= fifo_rd_data[DIN];
         o_hs <= fifo_rd_data[DIN+2];
         o_vs <= fifo_rd_data[DIN+1];
  end
endmodule
