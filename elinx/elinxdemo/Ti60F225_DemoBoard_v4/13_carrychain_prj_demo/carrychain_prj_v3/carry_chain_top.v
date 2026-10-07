module carry_chain_top #(
    parameter CARRY_NUM = 1,
    parameter TAP = 128
) (

 input clk_600m,
 input clk_100m,
 input clk_300m,

 output lvds_tx_TX_OE,
 input  lvds_rx_RX_DATA,
output reg [3:0] lvds_tx_TX_DATA,
 output lvds_tx_TX_RST,
 output lvds_rx_RX_ENA,
 output lvds_rx_RX_RST,

 input jtag_inst1_CAPTURE,
 input jtag_inst1_DRCK,
 input jtag_inst1_RESET,
 input jtag_inst1_RUNTEST,
 input jtag_inst1_SEL,
 input jtag_inst1_SHIFT,
 input jtag_inst1_TCK,
 input jtag_inst1_TDI,
 input jtag_inst1_TMS,
 input jtag_inst1_UPDATE,
 output jtag_inst1_TDO,
 output lvds_rx_RX_DLY_INC,
 output lvds_rx_RX_DLY_ENA,
 output lvds_rx_RX_DLY_RST
);
wire [TAP-1:0]  carry_tap  ;//
assign lvds_tx_TX_RST = 1'b0;
assign lvds_rx_RX_ENA = 1'b1;
assign lvds_tx_TX_OE = 1'b1;
assign lvds_rx_RX_RST = 1'b0;

//===================================================================== 
//tx data 
//========================================================================= 
wire send_en;

wire [5:0] dly_d;
wire dly_inc;
wire dly_en;
wire [5:0] dly_cnt;
wire mode;
(*syn_keep = "true"*)reg send_en_r_lock = 'd0;
(*syn_keep = "true"*)wire w_pos_send_lock;
always @( posedge clk_300m )
begin
    send_en_r_lock <= send_en;

end
assign w_pos_send_lock = (~send_en_r_lock) & send_en;

always @( posedge clk_300m )
begin
    lvds_tx_TX_DATA[0] <= w_pos_send_lock;
    lvds_tx_TX_DATA[3:1]  <= 3'd0;
end

// dyn_delay  dyn_delay_inst (
//     .clk(clk_300m),
//     .rst_n(1'b1),
//     .mode(mode),
//     .dyn_en(dly_en),
//     .dly_d(dly_d),
//     .dly_inc(dly_inc),
//     .dyn_rst(lvds_rx_RX_DLY_RST),
//     .dyn_inc(lvds_rx_RX_DLY_INC),
//     .dyn_ena(lvds_rx_RX_DLY_ENA),
//     .cal_busy(cal_busy),
//     .dly_cnt(dly_cnt )
//   );

//===================================================================== 
//rx data
//========================================================================= 


        carry_chain #(
        .TAP (TAP)
        )carry_chain_inst (
            .clk(clk_600m),
            .carry_in(lvds_rx_RX_DATA),
            .carry_tap(carry_tap)
        );


//
reg [4:0] cnt = 'd0;
reg send_en_r1_lock = 'd0;
always @( posedge clk_300m )
begin
    send_en_r1_lock <= send_en;

end
wire pos_send_sync = (~send_en_r1_lock) & send_en;
always @( posedge clk_600m )
begin
    if( pos_send_sync )
        cnt <= 'd0;
    else if(cnt[4] )  
        cnt <= cnt;
    else 
        cnt <= cnt + 1'b1;
end
reg [127:0] carry_tap0 [7:0];

always @( posedge clk_600m )
begin
    case(cnt )
    4'd2: begin
        carry_tap0[0] <=  carry_tap;
    end
    4'd3 : begin
        carry_tap0[1] <=  carry_tap;
    end
    4'd4 : begin
        carry_tap0[2] <=  carry_tap;
    end
    4'd5 : begin
        carry_tap0[3] <=  carry_tap;
    end
    4'd6 : begin
        carry_tap0[4] <=  carry_tap;
    end
    4'd7: begin
        carry_tap0[5] <=  carry_tap;
    end
    4'd8: begin
        carry_tap0[6] <=  carry_tap;
    end
    4'd9: begin
        carry_tap0[7] <=  carry_tap;
    end
    default:;
    endcase
end
reg [7:0] lef_zero_cnt ;
reg [7:0] right_zero_cnt ;
reg  [127:0] carry_tap_left;
reg [127:0] carry_tap_right;
reg [127:0] right_zero_cnt_r = 'd0;
reg [127:0] lef_zero_cnt_r = 'd0;
reg carry_tap_left_bit_r ;
reg carry_tap_right_bit_r;
wire pos_left_one = {carry_tap_left_bit_r,carry_tap_left[0]} == 2'b01;
wire pos_right_one = {carry_tap_right_bit_r,carry_tap_right[127]} == 2'b01;
always @( posedge clk_600m )
begin
    lef_zero_cnt <=  pos_left_one ? 0 : lef_zero_cnt + 1'b1;
    right_zero_cnt <=  pos_right_one? 0 : right_zero_cnt + 1'b1;
end
always @( posedge clk_600m )
begin 
    if( lef_zero_cnt == 0 )
        carry_tap_left <= carry_tap0[5];
    else 
        carry_tap_left <=  carry_tap_left >> 1;

        if( right_zero_cnt == 0 )
        carry_tap_right <= carry_tap0[5];
    else 
        carry_tap_right <=  carry_tap_right << 1;
end 
always @( posedge clk_600m )
begin
    carry_tap_left_bit_r <= carry_tap_left[0];
    carry_tap_right_bit_r <= carry_tap_right[127];
end

always @( posedge clk_600m )
begin
    if( pos_left_one)
        lef_zero_cnt_r <= lef_zero_cnt-1;

    if(pos_right_one )
        right_zero_cnt_r <= right_zero_cnt-1;
end

    edb_top edb_top_inst (
        .bscan_CAPTURE      ( jtag_inst1_CAPTURE ),
        .bscan_DRCK         ( jtag_inst1_DRCK ),
        .bscan_RESET        ( jtag_inst1_RESET ),
        .bscan_RUNTEST      ( jtag_inst1_RUNTEST ),
        .bscan_SEL          ( jtag_inst1_SEL ),
        .bscan_SHIFT        ( jtag_inst1_SHIFT ),
        .bscan_TCK          ( jtag_inst1_TCK ),
        .bscan_TDI          ( jtag_inst1_TDI ),
        .bscan_TMS          ( jtag_inst1_TMS ),
        .bscan_UPDATE       ( jtag_inst1_UPDATE ),
        .bscan_TDO          ( jtag_inst1_TDO ),
        
    
        .vio0_clk       ( clk_600m ),
        .vio0_carry_tap10(carry_tap0[4]),
        .vio0_carry_tap11(carry_tap0[5]),
        .vio0_carry_tap12(carry_tap0[6]),
        .vio0_carry_tap13(carry_tap0[7]),
        .vio0_left_0_cnt(lef_zero_cnt_r),
        .vio0_right_0_cnt(right_zero_cnt_r),


        .vio1_clk       ( clk_300m ),
        .vio1_send_en   ( send_en ),
        .vio1_dly_inc   (dly_inc),
        .vio1_dly_en    (dly_en),
        .vio1_dly_d     (dly_d),
        .vio1_mode     (mode),
        .vio1_dly_cnt   (dly_cnt),

        .la0_clk            ( clk_300m ),
        .la0_DLY_RST(lvds_rx_RX_DLY_RST),
        .la0_DLY_INC(lvds_rx_RX_DLY_INC),
        .la0_DLY_ENA(lvds_rx_RX_DLY_ENA),
        .la0_mode(mode),
        .la0_dly_cnt(dly_cnt)
    );




endmodule