// Display-only contrast diagnostic. Captured/DDR/accelerator pixels are unchanged.
// KEY1 selects a requested level; the active level changes only at (x,y)=(0,0).
// The RAW A/B/C/D means are measurements, never an automatic black-level offset.
module style_contrast_probe #(
    parameter integer DEBOUNCE_CYCLES = 1485000,
    parameter integer INITIAL_LEVEL = 2
) (
    input wire clk,
    input wire rst_n,
    input wire key1_n,
    input wire [15:0] x, y,
    input wire [23:0] input_rgb,
    input wire [39:0] cfa_means,
    input wire sample_valid,
    output reg [23:0] rgb,
    output reg [2:0] level
);
    localparam integer COUNT_BITS = (DEBOUNCE_CYCLES > 1) ? $clog2(DEBOUNCE_CYCLES) : 1;
    (* async_reg="true" *) reg key_meta, key_sync;
    reg debounced_key;
    reg [COUNT_BITS-1:0] debounce_count;
    reg [2:0] requested_level;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin key_meta <= 1; key_sync <= 1; end
        else begin key_meta <= key1_n; key_sync <= key_meta; end
    end
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            debounced_key <= 1; debounce_count <= 0;
            requested_level <= INITIAL_LEVEL; level <= INITIAL_LEVEL;
        end else begin
            if (key_sync == debounced_key) debounce_count <= 0;
            else if (debounce_count == DEBOUNCE_CYCLES-1) begin
                debounced_key <= key_sync;
                debounce_count <= 0;
                // Only the stable released->pressed edge counts. Holding KEY1
                // cannot repeat; release must also pass the same debounce.
                if (!key_sync)
                    requested_level <= requested_level == 4 ? 3'd0 : requested_level + 1'b1;
            end else debounce_count <= debounce_count + 1'b1;
            // A press accepted on this same edge takes effect next frame.
            if (x == 0 && y == 0) level <= requested_level;
        end
    end

    function [7:0] contrast8;
        input [7:0] value;
        input [2:0] setting;
        reg signed [12:0] centered, numerator, scaled;
        begin
            centered = $signed({1'b0,value}) - 13'sd128;
            // floor(((value-128)*gain_quarters + 512 + 2)/4).
            // Signed shifts/adds implement gain_quarters 4,5,6,7,8; the
            // arithmetic >>> is floor division even below zero, before clip.
            case (setting)
                0: numerator = (centered <<< 2) + 13'sd514;
                1: numerator = (centered <<< 2) + centered + 13'sd514;
                2: numerator = (centered <<< 2) + (centered <<< 1) + 13'sd514;
                3: numerator = (centered <<< 3) - centered + 13'sd514;
                default: numerator = (centered <<< 3) + 13'sd514;
            endcase
            scaled = numerator >>> 2;
            if (setting == 0) contrast8 = value;
            else if (scaled < 0) contrast8 = 0;
            else if (scaled > 255) contrast8 = 255;
            else contrast8 = scaled[7:0];
        end
    endfunction

    // The same 5x7 glyph convention as style_color_probe_overlay, scaled 2x.
    function [34:0] glyph;
        input [7:0] c;
        begin
            case(c)
                "A":glyph=35'b01110_10001_10001_11111_10001_10001_10001;
                "B":glyph=35'b11110_10001_10001_11110_10001_10001_11110;
                "C":glyph=35'b01111_10000_10000_10000_10000_10000_01111;
                "D":glyph=35'b11110_10001_10001_10001_10001_10001_11110;
                "E":glyph=35'b11111_10000_10000_11110_10000_10000_11111;
                "F":glyph=35'b11111_10000_10000_11110_10000_10000_10000;
                "G":glyph=35'b01111_10000_10000_10111_10001_10001_01111;
                "H":glyph=35'b10001_10001_10001_11111_10001_10001_10001;
                "I":glyph=35'b11111_00100_00100_00100_00100_00100_11111;
                "K":glyph=35'b10001_10010_10100_11000_10100_10010_10001;
                "L":glyph=35'b10000_10000_10000_10000_10000_10000_11111;
                "N":glyph=35'b10001_11001_10101_10011_10001_10001_10001;
                "O":glyph=35'b01110_10001_10001_10001_10001_10001_01110;
                "P":glyph=35'b11110_10001_10001_11110_10000_10000_10000;
                "R":glyph=35'b11110_10001_10001_11110_10100_10010_10001;
                "S":glyph=35'b01111_10000_10000_01110_00001_00001_11110;
                "T":glyph=35'b11111_00100_00100_00100_00100_00100_00100;
                "Y":glyph=35'b10001_10001_01010_00100_00100_00100_00100;
                "0":glyph=35'b01110_10001_10011_10101_11001_10001_01110;
                "1":glyph=35'b00100_01100_00100_00100_00100_00100_01110;
                "2":glyph=35'b01110_10001_00001_00010_00100_01000_11111;
                "3":glyph=35'b11110_00001_00001_01110_00001_00001_11110;
                "4":glyph=35'b00010_00110_01010_10010_11111_00010_00010;
                "5":glyph=35'b11111_10000_10000_11110_00001_00001_11110;
                "6":glyph=35'b01110_10000_10000_11110_10001_10001_01110;
                "7":glyph=35'b11111_00001_00010_00100_01000_01000_01000;
                "8":glyph=35'b01110_10001_10001_01110_10001_10001_01110;
                "9":glyph=35'b01110_10001_10001_01111_00001_00001_01110;
                ":":glyph=35'b00000_00100_00100_00000_00100_00100_00000;
                ".":glyph=35'b00000_00000_00000_00000_00000_00100_00100;
                "-":glyph=35'b00000_00000_00000_11111_00000_00000_00000;
                default:glyph=0;
            endcase
        end
    endfunction
    function [7:0] hex_char;
        input [3:0] nibble;
        begin hex_char=nibble<10 ? 8'd48+nibble : 8'd65+nibble-10; end
    endfunction
    function [7:0] title_char;
        input integer n;
        begin
            title_char=" ";
            case(n)
                0:title_char="C";1:title_char="O";2:title_char="N";3:title_char="T";
                4:title_char="R";5:title_char="A";6:title_char="S";7:title_char="T";
                9:title_char="P";10:title_char="R";11:title_char="O";
                12:title_char="B";13:title_char="E";15:title_char="0";16:title_char="1";
                default:;
            endcase
        end
    endfunction
    function [7:0] base_char;
        input integer n;
        begin
            base_char=" ";
            case(n)
                0:base_char="L";1:base_char="E";2:base_char="F";3:base_char="T";
                5:base_char="B";6:base_char="A";7:base_char="S";8:base_char="E";
                default:;
            endcase
        end
    endfunction
    function [7:0] gain_char;
        input integer n;
        input [2:0] setting;
        begin
            gain_char=" ";
            case(n)
                0:gain_char="R";1:gain_char="I";2:gain_char="G";3:gain_char="H";4:gain_char="T";
                6:gain_char=setting==4 ? "2" : "1";
                7:gain_char=".";
                8:case(setting)
                    1:gain_char="2";2:gain_char="5";3:gain_char="7";default:gain_char="0";
                  endcase
                9:gain_char=(setting==1 || setting==3) ? "5" : "0";
                11:gain_char="K";12:gain_char="E";13:gain_char="Y";14:gain_char="1";
                default:;
            endcase
        end
    endfunction

    integer local_x, local_y, index, col, row, field_pos;
    reg [7:0] character;
    reg [9:0] mean;
    reg [34:0] dots;
    reg text_area;
    always @* begin
        rgb=input_rgb;
        local_x=0;local_y=0;index=0;col=0;row=0;field_pos=0;
        character=" ";mean=0;dots=0;text_area=0;
        if (x>=640 && x<1280 && y>=120 && y<600)
            rgb={contrast8(input_rgb[23:16],level),contrast8(input_rgb[15:8],level),
                 contrast8(input_rgb[7:0],level)};

        if(y>=644 && y<658) begin
            if(x>=8 && x<8+17*12) begin
                local_x=x-8;local_y=y-644;text_area=1;
                character=title_char(local_x/12);
            end else if(x>=648 && x<648+9*12) begin
                local_x=x-648;local_y=y-644;text_area=1;
                character=base_char(local_x/12);
            end
        end else if(y>=664 && y<678) begin
            if(x>=8 && x<8+23*12) begin
                local_x=x-8;local_y=y-664;text_area=1;
                index=local_x/12;field_pos=index%6;
                case(index/6)
                    0:mean=cfa_means[9:0];
                    1:mean=cfa_means[19:10];
                    2:mean=cfa_means[29:20];
                    default:mean=cfa_means[39:30];
                endcase
                if(field_pos==0) character=8'd65+index/6;
                else if(field_pos==1) character=":";
                else if(field_pos>=2 && field_pos<=4)
                    character=sample_valid ? hex_char((mean >> ((4-field_pos)*4)) & 4'hF) : "-";
            end else if(x>=648 && x<648+15*12) begin
                local_x=x-648;local_y=y-664;text_area=1;
                character=gain_char(local_x/12,level);
            end
        end
        col=(local_x%12)/2;row=local_y/2;dots=glyph(character);
        if(text_area && col<5 && row<7 && dots[34-row*5-col]) rgb=24'hE0E0E0;

        // Standard references are direct display RGB, independent of the level.
        if(y>=692 && y<712 && x<1280) case(x[10:8])
            0:rgb=24'hFF0000;
            1:rgb=24'h00FF00;
            2:rgb=24'h0000FF;
            3:rgb=24'hFFFFFF;
            default:rgb=24'h808080;
        endcase
    end

`ifndef SYNTHESIS
    initial begin
        if(DEBOUNCE_CYCLES<1 || INITIAL_LEVEL<0 || INITIAL_LEVEL>4)
            $fatal(1,"Invalid contrast-probe debounce or initial level");
    end
`endif
endmodule
