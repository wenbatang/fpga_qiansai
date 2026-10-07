
module tx_aux( 
input            clk,    // pixel clock input
input            rst_p,    // async. reset input (active high)
input            i_hs,
input            i_vs,
input     [ 1:0] video_format,
input     [ 6:0] video_VIC,
input     [23:0] audio_L ,
input     [23:0] audio_R ,
input            audio_valid,
input  [19:0]    audio_N,
input  [19:0]    audio_CTS,
input [3:0]      audio_sample_frequency,     
input [3:0]      audio_word_length,


input            island_preamble,
input            island_lead_gb ,
input            data_island_period,
input            island_trail_gb,
input            video_preamble ,
input            video_lead_gb 	,

output reg [9:0]    ch0_dout,
output reg [9:0]    ch1_dout,
output reg [9:0]    ch2_dout
);

//Encryption begin
/*----------------------------------------------------------------------------------*\
                                 The main code
\*----------------------------------------------------------------------------------*/

reg [9:0] ch0_terc4 = 'd0;
reg [9:0] ch1_terc4 = 'd0;
reg [9:0] ch2_terc4 = 'd0;
wire [ 3:0] aux0_data ;

reg [4:0] pkt_cnt = 'd0;
wire fifo_rd_en;
reg pkg_valid = 'd0;

reg [55:0] r_BCH0 = 'd0;
reg [55:0] r_BCH1 = 'd0;
reg [55:0] r_BCH2 = 'd0;
reg [55:0] r_BCH3 = 'd0;
reg [23:0] r_BCH4 = 'd0;
reg [55:0] r1_BCH0 = 'd0;
reg [55:0] r1_BCH1 = 'd0;
reg [55:0] r1_BCH2 = 'd0;
reg [55:0] r1_BCH3 = 'd0;
reg [23:0] r1_BCH4 = 'd0;
wire [55:0] w_BCH0 ;
wire [55:0] w_BCH1 ;
wire [55:0] w_BCH2 ;
wire [55:0] w_BCH3 ;
wire [23:0] w_BCH4 ;
wire        fifo_rd_empty;


wire [23:0] avi_header;
wire [55:0] avi_sub0  ;
wire [55:0] avi_sub1  ;
wire [55:0] avi_sub2  ;
wire [55:0] avi_sub3  ;

wire [23:0] audio_clk_reg_header;
wire [55:0] audio_clk_reg_sub0;
wire [55:0] audio_clk_reg_sub1;
wire [55:0] audio_clk_reg_sub2;
wire [55:0] audio_clk_reg_sub3;
wire        audio_clk_reg_pkt_valid;
reg avi_pkt_valid;
auxiliary_video_information_info_frame auxiliary_video_information_info_frame_inst (
    .video_format(video_format),
    .video_VIC(video_VIC),
    .header(avi_header),
    .sub0  (avi_sub0  ),
    .sub1  (avi_sub1  ),
    .sub2  (avi_sub2  ),
    .sub3  (avi_sub3  )
  );

  always @( posedge clk )
  begin
    avi_pkt_valid <= audio_clk_reg_pkt_valid;
  end

// audio_infoframe_packet audio_infoframe_packet_inst (
//     .header(header),
//     .sub(sub)
//   );



audio_clock_regeneration_packet # (
    .VIDEO_RATE(1234)
  )
  audio_clock_regeneration_packet_inst (
    .clk(clk),
    .N      (audio_N),
    .CTS    (audio_CTS),
    .header (audio_clk_reg_header),
    .sub0   (audio_clk_reg_sub0),
    .sub1   (audio_clk_reg_sub1),
    .sub2   (audio_clk_reg_sub2),
    .sub3   (audio_clk_reg_sub3),
    .pkt_valid(audio_clk_reg_pkt_valid)
  );


wire [23:0]audio_header;
wire [55:0]audio_sub0  ;
wire [55:0]audio_sub1  ;
wire [55:0]audio_sub2  ;
wire [55:0]audio_sub3  ;
wire       audio_pkt_valid ;
audio_packet # (
    .CHANNEL_NUM(2),
    .GRADE(1'b0),
    .SAMPLE_WORD_TYPE(1'b0),
    .COPYRIGHT_NOT_ASSERTED(1'b1),
    .PRE_EMPHASIS(3'b000),
    .MODE(2'b00),
    .CATEGORY_CODE(8'd0),
    .SOURCE_NUMBER(4'd0),
    // .SAMPLING_FREQUENCY(4'b0000),
    .CLOCK_ACCURACY(2'b00),
    // .WORD_LENGTH(4'd0),
    .ORIGINAL_SAMPLING_FREQUENCY(4'd0),
    .LAYOUT(1'b0)
  )audio_packet_inst (
    .clk(clk),
    .rst_p(rst_p),
    // .frame_counter(frame_counter),
    .valid_bit_l(4'b0000),
    .valid_bit_r(4'b0000),
    .user_data_bit_l(4'b0000),
    .user_data_bit_r(4'b0000),
    .audio_valid(audio_valid),
    .audio_word_length(audio_word_length),
    .audio_sample_frequency(audio_sample_frequency),
    .audio_L0(audio_L),
    .audio_L1(24'd0),
    .audio_L2(24'd0),
    .audio_L3(24'd0),
    .audio_R0(audio_R),
    .audio_R1(24'd0),
    .audio_R2(24'd0),
    .audio_R3(24'd0),
    .audio_sample_word_present(4'b0001),
    .header(audio_header),
    .sub0  (audio_sub0  ),
    .sub1  (audio_sub1  ),
    .sub2  (audio_sub2  ),
    .sub3  (audio_sub3  ),
    .pkt_valid(audio_pkt_valid )
  );
  reg fifo_wr_en = 'd0;
  // reg pkt_header_flag_r0 = 'd0;
reg [1:0] r_vs = 'd0;
reg [1:0] r_hs = 'd0;

reg [1:0] island_preamble_r;
reg [1:0] island_lead_gb_r ;
reg [1:0] island_trail_gb_r;
reg [1:0] video_preamble_r ;
reg [1:0] video_lead_gb_r ;
reg [1:0] data_island_period_r;

  always @( * )
  begin
        if( audio_pkt_valid )
            {r_BCH4,r_BCH3,r_BCH2,r_BCH1,r_BCH0} = {audio_header,audio_sub3,audio_sub2,audio_sub1,audio_sub0};
        else if( audio_clk_reg_pkt_valid )
            {r_BCH4,r_BCH3,r_BCH2,r_BCH1,r_BCH0} = {audio_clk_reg_header,audio_clk_reg_sub3,audio_clk_reg_sub2,audio_clk_reg_sub1,audio_clk_reg_sub0};
        else if( avi_pkt_valid )
            {r_BCH4,r_BCH3,r_BCH2,r_BCH1,r_BCH0} = {avi_header,avi_sub3,avi_sub2,avi_sub1,avi_sub0};
        else 
          {r_BCH4,r_BCH3,r_BCH2,r_BCH1,r_BCH0} = 'd0;
  end
  always @( * )
  begin
    fifo_wr_en = audio_pkt_valid || audio_clk_reg_pkt_valid || avi_pkt_valid;
  end
//=======================================================================================
//
//=======================================================================================


  wire fifo_full;
  Sc_Fifo_Slr8  Sc_Fifo_Slr8_inst (
    .Sys_Clk(clk),
    .Sync_Clr(rst_p),
    .I_Wr_En(fifo_wr_en),
    .I_Wr_Data({r_BCH4,r_BCH3,r_BCH2,r_BCH1,r_BCH0}),
    .I_Rd_En(fifo_rd_en ),
    .O_Rd_Data({w_BCH4,w_BCH3,w_BCH2,w_BCH1,w_BCH0}),
    .O_Data_Num(),
    .O_Wr_Full(fifo_full ),
    .O_Rd_Empty(fifo_rd_empty ),
    .O_Fifo_Err()
  );
  wire pkt_header_flag;
  always @( posedge clk )
  begin
      if( data_island_period )
          pkt_cnt <= pkt_cnt + 1'b1;
      else 
          pkt_cnt <= 'd0;
  end
  
  assign pkt_header_flag = pkt_cnt == 0 && data_island_period;
  assign fifo_rd_en = pkt_header_flag && ~fifo_rd_empty;
  // reg pkt_valid_r0 = 'd0;
  
  always @( posedge clk )
  begin
      // pkt_valid_r0 <= fifo_rd_en;
      // pkt_header_flag_r0 <= pkt_header_flag;
      r_vs <= {r_vs[0],i_vs};
      r_hs <= {r_hs[0],i_hs};
      data_island_period_r <= {data_island_period_r[0],data_island_period};
      island_preamble_r<= {island_preamble_r[0],island_preamble};
      island_lead_gb_r <= {island_lead_gb_r[0],island_lead_gb};
      island_trail_gb_r<= {island_trail_gb_r[0],island_trail_gb};
      video_preamble_r <= {video_preamble_r[0],video_preamble};
      video_lead_gb_r  <= {video_lead_gb_r[0],video_lead_gb};
  end
  always @( posedge clk )
  begin
      if(fifo_rd_en)//！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！！
          {r1_BCH4,r1_BCH3,r1_BCH2,r1_BCH1,r1_BCH0} <= {w_BCH4,w_BCH3,w_BCH2,w_BCH1,w_BCH0};
      else if(pkt_header_flag)//( pkt_header_flag_r0 )
          {r1_BCH4,r1_BCH3,r1_BCH2,r1_BCH1,r1_BCH0} <= {24'h0,56'h0,56'h0,56'h0,56'h0};
  end

// reg [5:0] ecc_cnt = 'd0;
// reg valid = 'd0;
// always @( posedge clk )
// begin
//     ecc_cnt <= ecc_cnt + 1'b1;
//     valid <= &ecc_cnt;
// end
//   ecc_calc  ecc_calc_inst (
//     .clk(clk),
//     .rst_p(1'b0),
//     .valid(valid),
//     .idata(56'h88206d012d5a54),//8'h96//(56'h4cf7067efc21c5),//ee//(56'h081984c72dc67c),//1d//(56'h00fda564fae68f),//(56'h00efc481e44310),//
//     .ecc(ecc)
//   ); 

//   ecc_calc_v1  ecc1_calc_inst (
//     .clk(clk),
//     .rst_p(1'b0),
//     .valid(valid),
//     .idata(56'h88206d012d5a54),//8'h96//(56'h4cf7067efc21c5),//ee//(56'h081984c72dc67c),//1d//(56'h00fda564fae68f),//(56'h00efc481e44310),//
//     .ecc(ecc)
//   ); 




wire packet_header;
wire [3:0] ch1_packet_data;
wire [3:0] ch2_packet_data;
packet_assembler  packet_assembler_inst (
    .clk(clk),
    .rst_p(rst_p),
    .data_island_period(data_island_period_r[0]),//!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    .header(r1_BCH4),
    .sub0(r1_BCH0),//
    .sub1(r1_BCH1),//(56'd0),//
    .sub2(r1_BCH2),//(56'd0),//
    .sub3(r1_BCH3),//(56'd0),//
    .packet_header(packet_header),
    .ch1_packet_data(ch1_packet_data),
    .ch2_packet_data(ch2_packet_data),
    .cnt(cnt)
  );

     wire first_header =  data_island_period_r[1:0] == 2'b01;


assign aux0_data = {~first_header,packet_header,r_vs[0],r_hs[0]};//!!!!!!!!!!!!!!!
//====================================================================
// data island process
//====================================================================
always @( posedge clk )
begin
    case(aux0_data)
    4'b0000: ch0_terc4[9:0] <= 10'b1010011100;//29c
    4'b0001: ch0_terc4[9:0] <= 10'b1001100011;//263 
    4'b0010: ch0_terc4[9:0] <= 10'b1011100100;//2e4 
    4'b0011: ch0_terc4[9:0] <= 10'b1011100010;//2e2
    4'b0100: ch0_terc4[9:0] <= 10'b0101110001;//171
    4'b0101: ch0_terc4[9:0] <= 10'b0100011110;//11e
    4'b0110: ch0_terc4[9:0] <= 10'b0110001110;//18e
    4'b0111: ch0_terc4[9:0] <= 10'b0100111100;//13c
    4'b1000: ch0_terc4[9:0] <= 10'b1011001100;//2cc 
    4'b1001: ch0_terc4[9:0] <= 10'b0100111001;//139 
    4'b1010: ch0_terc4[9:0] <= 10'b0110011100;//19c 
    4'b1011: ch0_terc4[9:0] <= 10'b1011000110; //2c6
    4'b1100: ch0_terc4[9:0] <= 10'b1010001110; //18e
    4'b1101: ch0_terc4[9:0] <= 10'b1001110001; //271
    4'b1110: ch0_terc4[9:0] <= 10'b0101100011; //163
    4'b1111: ch0_terc4[9:0] <= 10'b1011000011; //2d3
    default:;
    endcase
end 

always @( posedge clk )
begin
    case(ch1_packet_data)
    4'b0000: ch1_terc4[9:0] <= 10'b1010011100; 
    4'b0001: ch1_terc4[9:0] <= 10'b1001100011; 
    4'b0010: ch1_terc4[9:0] <= 10'b1011100100; 
    4'b0011: ch1_terc4[9:0] <= 10'b1011100010; 
    4'b0100: ch1_terc4[9:0] <= 10'b0101110001; 
    4'b0101: ch1_terc4[9:0] <= 10'b0100011110; 
    4'b0110: ch1_terc4[9:0] <= 10'b0110001110; 
    4'b0111: ch1_terc4[9:0] <= 10'b0100111100; 
    4'b1000: ch1_terc4[9:0] <= 10'b1011001100; 
    4'b1001: ch1_terc4[9:0] <= 10'b0100111001; 
    4'b1010: ch1_terc4[9:0] <= 10'b0110011100; 
    4'b1011: ch1_terc4[9:0] <= 10'b1011000110; 
    4'b1100: ch1_terc4[9:0] <= 10'b1010001110; 
    4'b1101: ch1_terc4[9:0] <= 10'b1001110001; 
    4'b1110: ch1_terc4[9:0] <= 10'b0101100011; 
    4'b1111: ch1_terc4[9:0] <= 10'b1011000011; 
    default:;
    endcase
end 

always @( posedge clk )
begin
    case(ch2_packet_data)
    4'b0000: ch2_terc4[9:0] <= 10'b1010011100; 
    4'b0001: ch2_terc4[9:0] <= 10'b1001100011; 
    4'b0010: ch2_terc4[9:0] <= 10'b1011100100; 
    4'b0011: ch2_terc4[9:0] <= 10'b1011100010; 
    4'b0100: ch2_terc4[9:0] <= 10'b0101110001; 
    4'b0101: ch2_terc4[9:0] <= 10'b0100011110; 
    4'b0110: ch2_terc4[9:0] <= 10'b0110001110; 
    4'b0111: ch2_terc4[9:0] <= 10'b0100111100; 
    4'b1000: ch2_terc4[9:0] <= 10'b1011001100; 
    4'b1001: ch2_terc4[9:0] <= 10'b0100111001; 
    4'b1010: ch2_terc4[9:0] <= 10'b0110011100; 
    4'b1011: ch2_terc4[9:0] <= 10'b1011000110; 
    4'b1100: ch2_terc4[9:0] <= 10'b1010001110; 
    4'b1101: ch2_terc4[9:0] <= 10'b1001110001; 
    4'b1110: ch2_terc4[9:0] <= 10'b0101100011; 
    4'b1111: ch2_terc4[9:0] <= 10'b1011000011; 
    default:;
    endcase
end 
//====================================================================
// control period
//====================================================================


always @(posedge clk )
begin
    case({island_lead_gb_r[1],data_island_period_r[1],island_trail_gb_r[1],video_lead_gb_r[1],video_preamble_r[1],island_preamble_r[1]})
        6'b000100: begin//video lead guardband
            ch0_dout <= 10'h2cc;
            ch1_dout <= 10'h133;
            ch2_dout <= 10'h2cc;
        end
        6'b100000,6'b001000: begin // island_gb
            case( {r_vs[1],r_hs[1] })
            2'b00 : ch0_dout <= 10'h28e;
            2'b01 : ch0_dout <= 10'h271;
            2'b10 : ch0_dout <= 10'h163;
            2'b11 : ch0_dout <= 10'h2c3;
            default :;
            endcase
            ch1_dout <=  10'h133;
            ch2_dout <=  10'h133;
      end
      6'b010000 : begin // data_island_period
            ch0_dout <= ch0_terc4;
            ch1_dout <= ch1_terc4;
            ch2_dout <= ch2_terc4;
      end
      6'b000001: begin //data island preamble
            
            case( {r_vs[1],r_hs[1] })
            2'b00 : ch0_dout <= 10'h354;
            2'b01 : ch0_dout <= 10'h0ab;
            2'b10 : ch0_dout <= 10'h154;
            2'b11 : ch0_dout <= 10'h2ab;
            default :;
            endcase
            ch1_dout <= 10'h0ab;
            ch2_dout <= 10'h0ab;
      end
      6'b000010: begin//video data preamble
        case( {r_vs[1],r_hs[1] })
        2'b00 : ch0_dout <= 10'h354;
        2'b01 : ch0_dout <= 10'h0ab;
        2'b10 : ch0_dout <= 10'h154;
        2'b11 : ch0_dout <= 10'h2ab;
        default :;
        endcase
        ch1_dout <= 10'h0ab;
        ch2_dout <= 10'h354;
      end
      default: begin
            case( {r_vs[1],r_hs[1] })
            2'b00 : ch0_dout <= 10'h354;
            2'b01 : ch0_dout <= 10'h0ab;
            2'b10 : ch0_dout <= 10'h154;
            2'b11 : ch0_dout <= 10'h2ab;
            default :;
            endcase
            ch1_dout <= 10'h354;//0ab;
            ch2_dout <= 10'h354;//0ab;
      end   
    endcase
end
//====================================================================
// 
//====================================================================

endmodule

//Encryption end