// Periodic, atomic camera diagnostic snapshot on a separate UART TX.
// All inputs belong to clk. Synchronous, active-high reset must be the DDR/UI
// domain reset and must NOT wait for DDR calibration. No RX, FIFO, RAM or DSP.
// fields = {boot, flags, good_lines, error_packets, ppi_ui_events, last_header,
//           capture_frames, inference_frames, capture_errors, raw_groups,
//           vs_edges, engine_cycles, trace[383:0]}; boot is [767:736].
// First 24 fields retain CAM2; append source count/R/G/B, output count/R/G/B, mode.
// First 24 fields are defined by camera_trace.py; all fields are 32 bits.
// Format: "@CAM4," + thirty-three uppercase, zero-padded HEX32 fields + CR LF.
// CAM4 mode word:raw bit0, engine_raw bit1, loaded[7:2], requested[13:8], front_raw bit14.
// Exactly 304 bytes. First report starts immediately after reset release.
// PERIOD_CYCLES measures report-start opportunities. A busy deadline is skipped;
// an in-flight snapshot is never replaced or queued. UART is 8N1, idle high.
module camera_view_uart #(
    parameter integer CLK_HZ = 100000000,
    parameter integer BAUD = 115200,
    parameter integer PERIOD_CYCLES = 100000000
)(
    input wire clk,
    input wire reset,
    input wire [1055:0] fields,
    output reg tx
);
    localparam integer DIVISOR = (CLK_HZ + BAUD/2) / BAUD;
    localparam integer BIT_W = DIVISOR > 1 ? $clog2(DIVISOR) : 1;
    localparam integer PERIOD_W = PERIOD_CYCLES > 1 ? $clog2(PERIOD_CYCLES) : 1;
    localparam [2:0] PREFIX=0, HEX=1, COMMA=2, CR=3, LF=4;
    reg [PERIOD_W-1:0] period_count;
    reg first_pending, active, tx_busy;
    reg [1055:0] snapshot;
    reg [2:0] phase, prefix_index, nibble_index;
    reg [5:0] field_index;
    reg [3:0] bit_index;
    reg [BIT_W-1:0] bit_count;
    reg [9:0] tx_shift;
    reg [31:0] selected_field;
    reg [3:0] nibble;
    reg [7:0] next_byte;

    // Explicit constant slices avoid division, a multiplier or inferred memory.
    always @* begin
        case (field_index)
            0:selected_field=snapshot[1055:1024];
            1:selected_field=snapshot[1023:992];
            2:selected_field=snapshot[991:960];
            3:selected_field=snapshot[959:928];
            4:selected_field=snapshot[927:896];
            5:selected_field=snapshot[895:864];
            6:selected_field=snapshot[863:832];
            7:selected_field=snapshot[831:800];
            8:selected_field=snapshot[799:768];
            9:selected_field=snapshot[767:736];
            10:selected_field=snapshot[735:704];
            11:selected_field=snapshot[703:672];
            12:selected_field=snapshot[671:640];
            13:selected_field=snapshot[639:608];
            14:selected_field=snapshot[607:576];
            15:selected_field=snapshot[575:544];
            16:selected_field=snapshot[543:512];
            17:selected_field=snapshot[511:480];
            18:selected_field=snapshot[479:448];
            19:selected_field=snapshot[447:416];
            20:selected_field=snapshot[415:384];
            21:selected_field=snapshot[383:352];
            22:selected_field=snapshot[351:320];
            23:selected_field=snapshot[319:288];
            24:selected_field=snapshot[287:256];
            25:selected_field=snapshot[255:224];
            26:selected_field=snapshot[223:192];
            27:selected_field=snapshot[191:160];
            28:selected_field=snapshot[159:128];
            29:selected_field=snapshot[127:96];
            30:selected_field=snapshot[95:64];
            31:selected_field=snapshot[63:32];
            default:selected_field=snapshot[31:0];
        endcase
        case (nibble_index)
            0:nibble=selected_field[31:28];
            1:nibble=selected_field[27:24];
            2:nibble=selected_field[23:20];
            3:nibble=selected_field[19:16];
            4:nibble=selected_field[15:12];
            5:nibble=selected_field[11:8];
            6:nibble=selected_field[7:4];
            default:nibble=selected_field[3:0];
        endcase
        next_byte=8'hff;
        case (phase)
            PREFIX:case(prefix_index)
                0:next_byte=8'h40; // @
                1:next_byte=8'h43; // C
                2:next_byte=8'h41; // A
                3:next_byte=8'h4d; // M
                4:next_byte=8'h34; // 4: extended47-mode identity
                default:next_byte=8'h2c;
            endcase
            HEX:next_byte=nibble<10 ? 8'h30+{4'd0,nibble} : 8'h41+{4'd0,nibble}-8'd10;
            COMMA:next_byte=8'h2c;
            CR:next_byte=8'h0d;
            LF:next_byte=8'h0a;
            default:next_byte=8'hff;
        endcase
    end

    always @(posedge clk) begin
        if (reset) begin
            tx<=1'b1; tx_shift<=10'h3ff; tx_busy<=0;
            bit_count<=0; bit_index<=0;
            period_count<=0; first_pending<=1; active<=0; snapshot<=0;
            phase<=PREFIX; prefix_index<=0; field_index<=0; nibble_index<=0;
        end else begin
            if (first_pending || period_count==0) begin
                period_count<=PERIOD_CYCLES-1;
                first_pending<=0;
                if (!active && !tx_busy) begin
                    snapshot<=fields; active<=1;
                    phase<=PREFIX; prefix_index<=0; field_index<=0; nibble_index<=0;
                end
            end else period_count<=period_count-1'b1;

            if (!tx_busy) begin
                tx<=1'b1;
                if (active) begin
                    tx<=1'b0;
                    tx_shift<={1'b1,next_byte,1'b0};
                    tx_busy<=1; bit_count<=DIVISOR-1; bit_index<=0;
                end
            end else if (bit_count!=0) bit_count<=bit_count-1'b1;
            else if (bit_index!=9) begin
                tx<=tx_shift[1]; tx_shift<={1'b1,tx_shift[9:1]};
                bit_count<=DIVISOR-1; bit_index<=bit_index+1'b1;
            end else begin
                tx<=1'b1; tx_busy<=0;
                case (phase)
                    PREFIX:if(prefix_index==5)begin phase<=HEX;nibble_index<=0;end
                           else prefix_index<=prefix_index+1'b1;
                    HEX:if(nibble_index==7)begin
                            if(field_index==32)phase<=CR;else phase<=COMMA;
                        end else nibble_index<=nibble_index+1'b1;
                    COMMA:begin field_index<=field_index+1'b1;nibble_index<=0;phase<=HEX;end
                    CR:phase<=LF;
                    LF:active<=0;
                    default:active<=0;
                endcase
            end
        end
    end
endmodule
