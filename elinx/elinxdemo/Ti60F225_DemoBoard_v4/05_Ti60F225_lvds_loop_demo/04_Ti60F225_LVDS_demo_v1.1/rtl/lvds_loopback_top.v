/////////////////////////////////////////////////////////////////////////////
//
// Copyright (C) 2013-2019 Efinix Inc. All rights reserved.
//
// lvds_loopback_top.v
//
// *******************************
// Revisions:
// 1.0 Initial rev
//
// *******************************
/////////////////////////////////////////////////////////////////////////////


module lvds_loopback_top (
  input txpll_locked,
  input	rxpll_locked,
  input rx_fast_clk,
  input rx_slow_clk,
  input tx_slow_clk,
  input tx_fast_clk,
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
  
  output lvds_tx_pll_RSTN,
  output reg lvds_rx_pll_RSTN,
  
  input [7:0] lvds_rx_d0_RX_DATA,
  input [7:0] lvds_rx_d1_RX_DATA,   
  input [7:0] lvds_rx_d2_RX_DATA,
  input [7:0] lvds_rx_d3_RX_DATA,
  input tx_refclk_50M,
  input clk_25m,
  
  output lvds_rx_clk_RX_ENA,
  output lvds_rx_d0_RX_RST,
  output lvds_rx_d0_RX_ENA,
  output lvds_rx_d1_RX_RST,
  output lvds_rx_d1_RX_ENA,
  output lvds_rx_d2_RX_RST,
  output lvds_rx_d2_RX_ENA,
  output lvds_rx_d3_RX_RST,
  output lvds_rx_d3_RX_ENA,
  
  output lvds_tx_clk_TX_RST,
  output lvds_tx_d0_TX_RST,
  output lvds_tx_d1_TX_RST, 
  output lvds_tx_d2_TX_RST,
  output lvds_tx_d3_TX_RST,
  output lvds_tx_clk_TX_OE,
  output lvds_tx_d0_TX_OE,
  output lvds_tx_d1_TX_OE,
  output lvds_tx_d2_TX_OE,
  output lvds_tx_d3_TX_OE,
  output reg [7:0] lvds_tx_d0_TX_DATA,
  output reg [7:0] lvds_tx_d1_TX_DATA,  
  output reg [7:0] lvds_tx_d2_TX_DATA,
  output reg [7:0] lvds_tx_d3_TX_DATA,
  output 		 [7:0] lvds_tx_clk_TX_DATA,
  output lvds_rx_d0_RX_DLY_INC,
  output lvds_rx_d0_RX_DLY_ENA,
  output lvds_rx_d0_RX_DLY_RST,
  output lvds_rx_d1_RX_DLY_INC,
  output lvds_rx_d1_RX_DLY_ENA,
  output lvds_rx_d1_RX_DLY_RST,    
  output lvds_rx_d2_RX_DLY_INC,
	output lvds_rx_d2_RX_DLY_ENA,
	output lvds_rx_d2_RX_DLY_RST,
	output lvds_rx_d3_RX_DLY_INC,
	output lvds_rx_d3_RX_DLY_ENA,
	output lvds_rx_d3_RX_DLY_RST,


  
  
  output	[3:0] led
);


assign	lvds_rx_clk_RX_ENA = 1'b1;
assign	lvds_rx_d0_RX_ENA = 1'b1;
assign	lvds_rx_d1_RX_ENA = 1'b1;   
assign	lvds_rx_d2_RX_ENA = 1'b1;
assign	lvds_rx_d3_RX_ENA = 1'b1;
assign 	lvds_rx_d0_RX_RST = 1'b0;
assign 	lvds_rx_d1_RX_RST = 1'b0;     
assign 	lvds_rx_d2_RX_RST = 1'b0;
assign 	lvds_rx_d3_RX_RST = 1'b0;


wire        [7:0]   lvds_rx_data_slip0  ;
wire        [7:0]   lvds_rx_data_slip1  ;
wire        [7:0]   lvds_rx_data_slip2  ;
wire        [7:0]   lvds_rx_data_slip3  ;

reg                 bitslip0            ;
reg                 bitslip1            ;
reg                 bitslip2            ;
reg                 bitslip3            ;

wire                vio_bitslip0        ;
wire                vio_bitslip1        ;
wire                vio_bitslip2        ;
wire                vio_bitslip3        ;
                                       
wire                bitslip_all         ;
wire                bitslip_binding     ;

wire                stat0               ;
wire                stat1               ;
wire                stat2               ;
wire                stat3               ;

wire                stat_all            ;
wire                pll_locked          ;
reg                 det_pass            ;
wire                rx_rstn, tx_rstn    ;
wire        [7:0]   prbs_data           ;
wire        [7:0]   vio_lvds_tx_data    ;
wire                data_source         ;
reg					[7:0]		cnt 								;


assign              rx_rstn = rxpll_locked ;
assign              tx_rstn = txpll_locked ;
//=================================================================
/////// PRBS GENERATOR //////
assign	lvds_tx_pll_RSTN 	= 1'b1;
assign	lvds_tx_d0_TX_RST = 1'b0;
assign	lvds_tx_d1_TX_RST = 1'b0;    
assign	lvds_tx_d2_TX_RST = 1'b0;
assign	lvds_tx_d3_TX_RST = 1'b0;
assign	lvds_tx_d0_TX_OE  = 1'b1;
assign	lvds_tx_d1_TX_OE  = 1'b1; 
assign	lvds_tx_d2_TX_OE  = 1'b1;
assign	lvds_tx_d3_TX_OE  = 1'b1;
assign 	lvds_tx_clk_TX_DATA = 8'hf0;
assign	lvds_tx_clk_TX_RST= 1'b0;
assign	lvds_tx_clk_TX_OE = 1'b1;


prbs_gen prbs_gen_inst(
    .clk    (tx_slow_clk             ),
    .rstn   (tx_rstn                ),
    .out    (prbs_data              )
);



///////////data_source switch///////////
always @(posedge tx_slow_clk or negedge tx_rstn) begin
    if (!tx_rstn) begin
        lvds_tx_d0_TX_DATA <= 8'h0;
        lvds_tx_d1_TX_DATA <= 8'h0;
        lvds_tx_d1_TX_DATA <= 8'h0;
        lvds_tx_d1_TX_DATA <= 8'h0;
    end else begin
        if (data_source) begin
            lvds_tx_d0_TX_DATA <= prbs_data;
            lvds_tx_d1_TX_DATA <= prbs_data; 
            lvds_tx_d2_TX_DATA <= prbs_data;
            lvds_tx_d3_TX_DATA <= prbs_data;
        end else begin
            lvds_tx_d0_TX_DATA <= vio_lvds_tx_data;
            lvds_tx_d1_TX_DATA <= vio_lvds_tx_data; 
            lvds_tx_d2_TX_DATA <= vio_lvds_tx_data;
            lvds_tx_d3_TX_DATA <= vio_lvds_tx_data;
        end
    end
end





/*******************LVDS rx1 ************/
// Frame bitslip 
reg [7:0] lvds_rx_d0_RX_DATA_d0;
reg [7:0] lvds_rx_d1_RX_DATA_d0;
reg [7:0] lvds_rx_d2_RX_DATA_d0;
reg [7:0] lvds_rx_d3_RX_DATA_d0;
always @( posedge rx_slow_clk )
begin
    lvds_rx_d0_RX_DATA_d0 <= lvds_rx_d0_RX_DATA;
    lvds_rx_d1_RX_DATA_d0 <= lvds_rx_d1_RX_DATA;
    lvds_rx_d2_RX_DATA_d0 <= lvds_rx_d2_RX_DATA;
    lvds_rx_d3_RX_DATA_d0 <= lvds_rx_d3_RX_DATA;

end
frame_bitslip frame_bitslip_inst1(
    .clk        (rx_slow_clk         ),
    .rstn       (rx_rstn            ),
    .bitslip    (bitslip0           ),
    .data_in    (lvds_rx_d0_RX_DATA_d0 ),
    .data_out   (lvds_rx_data_slip0 )
);

//  PRBS checker 
prbs_det prbs_det_inst1(
    .clk        (rx_slow_clk         ),
    .rstn       (rx_rstn            ),
    .data       (lvds_rx_data_slip0 ),
    .testen     (1'b1               ),
    .stat       (stat0              )
);
wire dly_en0;    
wire dly_en1;   
wire dly_en2;    
wire dly_en3; 

wire [5:0] dly_d0;   
wire [5:0] dly_d1;
wire [5:0] dly_d2;   
wire [5:0] dly_d3;

dyn_delay u_dyn_delay(
/*i*/.clk				(rx_slow_clk					),
/*i*/.rst_n			(rx_rstn							),
/*i*/.dyn_en		(	dly_en0				),
/*i*/.dly_d			(	dly_d0				),
/*i*/.dly_inc		(1'b1),
/*o*/.dyn_rst		(lvds_rx_d0_RX_DLY_RST),
/*o*/.dyn_inc		(lvds_rx_d0_RX_DLY_INC),
/*o*/.dyn_ena		(lvds_rx_d0_RX_DLY_ENA),
/*o*/.cal_busy	()

);

dyn_delay u1_dyn_delay(
/*i*/.clk				(rx_slow_clk					),
/*i*/.rst_n			(rx_rstn							),
/*i*/.dyn_en		(	dly_en1				),
/*i*/.dly_d			(	dly_d1				),
/*i*/.dly_inc		(1'b1),
/*o*/.dyn_rst		(lvds_rx_d1_RX_DLY_RST),
/*o*/.dyn_inc		(lvds_rx_d1_RX_DLY_INC),
/*o*/.dyn_ena		(lvds_rx_d1_RX_DLY_ENA),
/*o*/.cal_busy	()

);

dyn_delay u2_dyn_delay(
/*i*/.clk				(rx_slow_clk					),
/*i*/.rst_n			(rx_rstn							),
/*i*/.dyn_en		(	dly_en2				),
/*i*/.dly_d			(	dly_d2				),
/*i*/.dly_inc		(1'b1),
/*o*/.dyn_rst		(lvds_rx_d2_RX_DLY_RST),
/*o*/.dyn_inc		(lvds_rx_d2_RX_DLY_INC),
/*o*/.dyn_ena		(lvds_rx_d2_RX_DLY_ENA),
/*o*/.cal_busy	()

);

dyn_delay u3_dyn_delay(
/*i*/.clk				(rx_slow_clk					),
/*i*/.rst_n			(rx_rstn							),
/*i*/.dyn_en		(	dly_en3				),
/*i*/.dly_d			(	dly_d3				),
/*i*/.dly_inc		(1'b1),
/*o*/.dyn_rst		(lvds_rx_d3_RX_DLY_RST),
/*o*/.dyn_inc		(lvds_rx_d3_RX_DLY_INC),
/*o*/.dyn_ena		(lvds_rx_d3_RX_DLY_ENA),
/*o*/.cal_busy	()

);

/*******************LVDS rx2 ************/
// Frame bitslip 
frame_bitslip frame_bitslip_inst2(
    .clk        (rx_slow_clk         ),
    .rstn       (rx_rstn            ),
    .bitslip    (bitslip1           ),
    .data_in    (lvds_rx_d1_RX_DATA_d0      ),
    .data_out   (lvds_rx_data_slip1 )
);

//  PRBS checker 
prbs_det prbs_det_inst2(
    .clk        (rx_slow_clk         ),
    .rstn       (rx_rstn            ),
    .data       (lvds_rx_data_slip1 ),
    .testen     (1'b1               ),
    .stat       (stat1              )
);

/*******************LVDS rx3 ************/
// Frame bitslip 
frame_bitslip frame_bitslip_inst3(
    .clk        (rx_slow_clk         ),
    .rstn       (rx_rstn            ),
    .bitslip    (bitslip2           ),
    .data_in    (lvds_rx_d2_RX_DATA_d0      ),
    .data_out   (lvds_rx_data_slip2 )
);

//  PRBS checker 
prbs_det prbs_det_inst3(
    .clk        (rx_slow_clk         ),
    .rstn       (rx_rstn            ),
    .data       (lvds_rx_data_slip2 ),
    .testen     (1'b1               ),
    .stat       (stat2              )
);
/*******************LVDS rx4 ************/
// Frame bitslip 
frame_bitslip frame_bitslip_inst4(
    .clk        (rx_slow_clk         ),
    .rstn       (rx_rstn            ),
    .bitslip    (bitslip3           ),
    .data_in    (lvds_rx_d3_RX_DATA_d0      ),
    .data_out   (lvds_rx_data_slip3 )
);

//  PRBS checker 
prbs_det prbs_det_inst4(
    .clk        (rx_slow_clk         ),
    .rstn       (rx_rstn            ),
    .data       (lvds_rx_data_slip3 ),
    .testen     (1'b1               ),
    .stat       (stat3              )
);




always @(posedge rx_slow_clk or negedge rx_rstn) begin
    if (!rx_rstn) begin
        bitslip0 <= 1'b0;
        bitslip1 <= 1'b0;
        bitslip2 <= 1'b0;
        bitslip3 <= 1'b0;
    end else begin
        if (bitslip_binding) begin
            bitslip0 <= bitslip_all;
            bitslip1 <= bitslip_all;
            bitslip2 <= bitslip_all;
            bitslip3 <= bitslip_all;
        end else begin
            bitslip0 <= vio_bitslip0;
            bitslip1 <= vio_bitslip1;
            bitslip2 <= vio_bitslip2;
            bitslip3 <= vio_bitslip3;
            
        end
    end
end



/////////// Pass det ////////////////////
reg [9:0] pass_cnt;
assign stat_all = stat1 & stat2 & stat3 & stat0;
always @(posedge rx_slow_clk or negedge rx_rstn) begin
    if (!rx_rstn) begin
        pass_cnt <= 10'h000;
    end else begin
        if (stat_all) begin
            if (pass_cnt == 10'h3FF) begin
                pass_cnt <= 10'h000;
            end else begin
                pass_cnt <= pass_cnt + 10'b1;
            end
        end else begin
            pass_cnt <= 10'h000;
        end
    end
end


always @(posedge rx_slow_clk or negedge rx_rstn) begin
    if (!rx_rstn) begin
        det_pass <= 1'b0;
    end else begin
        if (stat_all) begin
            if (pass_cnt == 10'h3FF) begin
                det_pass <= 1'b1;
            end else begin
                det_pass <= det_pass;
            end
        end else begin
            det_pass <= 1'b0;
        end
    end
end


////////////////heart beat//////////////////
reg [25:0] tx_clk_cnt;
reg tx_heartbeat;
always @(posedge tx_slow_clk or negedge tx_rstn) begin
    if (!tx_rstn) begin
        tx_heartbeat <= 1'b1;
        tx_clk_cnt <= 26'b0;
        end 
    else begin
        tx_heartbeat <= tx_clk_cnt[25];
        tx_clk_cnt <= tx_clk_cnt + 1'b1;
        end
end

always @( posedge tx_slow_clk or negedge tx_rstn )
begin
		if( !tx_rstn )
			lvds_rx_pll_RSTN  <=  1'b0;
		else if( &tx_clk_cnt && ~rxpll_locked) //
			lvds_rx_pll_RSTN  <=  1'b0;
        else
            lvds_rx_pll_RSTN <= 1'b1;
end

reg [25:0] rx_clk_cnt;
reg rx_heartbeat;
always @(posedge rx_slow_clk or negedge rx_rstn) begin
    if (!rx_rstn) begin
        rx_heartbeat <= 1'b1;
        rx_clk_cnt <= 26'b0;
        end 
    else begin
        rx_heartbeat <= rx_clk_cnt[25];
        rx_clk_cnt <= rx_clk_cnt + 1'b1;
        end
end


assign pll_locked = rxpll_locked && txpll_locked;

//////////////// USER_LEDS //////////////////
assign led [0] = ~det_pass;
assign led [1] = ~pll_locked;
assign led [2] = tx_heartbeat; 
assign led [3] = rx_heartbeat; 

debug_profile_edb_top edb_top_inst (
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
    .LVDS_TX_clk            ( tx_slow_clk ),
    .LVDS_TX_lvds_tx_data0      ( lvds_tx_d0_TX_DATA ),
    .LVDS_TX_lvds_tx_data1      ( lvds_tx_d1_TX_DATA ),
    .LVDS_TX_lvds_tx_data2      ( lvds_tx_d2_TX_DATA ),
    .LVDS_TX_lvds_tx_data3      ( lvds_tx_d3_TX_DATA ),
    .LVDS_RX_clk                ( rx_slow_clk ),
    // .LVDS_RX_lvds_rx_data0      ( lvds_rx_d0_RX_DATA ),
    // .LVDS_RX_lvds_rx_data1      ( lvds_rx_d1_RX_DATA ),
    // .LVDS_RX_lvds_rx_data2      ( lvds_rx_d2_RX_DATA ),
    // .LVDS_RX_lvds_rx_data3      ( lvds_rx_d3_RX_DATA ),
    .LVDS_RX_lvds_rx_data_slip0     ( lvds_rx_data_slip0 ),
    .LVDS_RX_lvds_rx_data_slip1     ( lvds_rx_data_slip1 ), 
    .LVDS_RX_lvds_rx_data_slip2     ( lvds_rx_data_slip2 ), 
    .LVDS_RX_lvds_rx_data_slip3     ( lvds_rx_data_slip3 ), 
    
    .LVDS_RX_stat0     ( stat0 ),
    .LVDS_RX_stat1     ( stat1 ),
    .LVDS_RX_stat2     ( stat2 ),
    .LVDS_RX_stat3     ( stat3 ),

    .vio_ctrl_status_clk                ( rx_slow_clk ),
    .vio_ctrl_status_pll_locked         ( pll_locked ),
    .vio_ctrl_status_rx_heartbeat       ( rx_heartbeat ),
    .vio_ctrl_status_tx_heartbeat       ( tx_heartbeat ),
    .vio_ctrl_status_det_pass           ( det_pass ),
    .vio_ctrl_status_stat0              ( stat0 ),
    .vio_ctrl_status_stat1              ( stat1 ),
    .vio_ctrl_status_stat2              ( stat2 ),
    .vio_ctrl_status_stat3              ( stat3 ),
    .vio_ctrl_status_data_source        ( data_source ),
    .vio_ctrl_status_lvds_tx_data       ( vio_lvds_tx_data ),
    .vio_ctrl_status_bitslip_binding    ( bitslip_binding ),
    .vio_ctrl_status_bitslip_all        ( bitslip_all ),
    .vio_ctrl_status_bitslip0           ( vio_bitslip0 ),
    .vio_ctrl_status_bitslip1           ( vio_bitslip1 ),
    .vio_ctrl_status_bitslip2           ( vio_bitslip2 ),
    .vio_ctrl_status_bitslip3           ( vio_bitslip3 ),
    // .vio_ctrl_status_dly_en0							( dly_en0),        
    // .vio_ctrl_status_dly_d0							( dly_d0 ),    
    // .vio_ctrl_status_dly_en1							( dly_en1),
    // .vio_ctrl_status_dly_d1							( dly_d1 ),   
    // .vio_ctrl_status_dly_en2							( dly_en2),
    // .vio_ctrl_status_dly_d2							( dly_d2 ), 
    // .vio_ctrl_status_dly_en3							( dly_en3),
    // .vio_ctrl_status_dly_d3							( dly_d3 ),  
    
    .vio_tx_data_clk                    ( tx_slow_clk ),
    .vio_tx_data_lvds_tx_data0          ( lvds_tx_d0_TX_DATA ),
    .vio_tx_data_lvds_tx_data1          ( lvds_tx_d1_TX_DATA ),
    .vio_tx_data_lvds_tx_data2          ( lvds_tx_d2_TX_DATA ),
    .vio_tx_data_lvds_tx_data3          ( lvds_tx_d3_TX_DATA ),

    
    .vio_rx_data_clk                    ( rx_slow_clk ),
    .vio_rx_data_lvds_rx_data0          ( lvds_rx_d0_RX_DATA ),
    .vio_rx_data_lvds_rx_data1          ( lvds_rx_d1_RX_DATA ),
    .vio_rx_data_lvds_rx_data2          ( lvds_rx_d2_RX_DATA ),
	.vio_rx_data_lvds_rx_data3          ( lvds_rx_d3_RX_DATA ),
    .vio_rx_data_lvds_rx_data_slip0     ( lvds_rx_data_slip0 ),
    .vio_rx_data_lvds_rx_data_slip1     ( lvds_rx_data_slip1 ),
    .vio_rx_data_lvds_rx_data_slip2     ( lvds_rx_data_slip2 ),
    .vio_rx_data_lvds_rx_data_slip3     ( lvds_rx_data_slip3 )
);





endmodule

