// Combinational 5x7 glyphs, scaled 2x. No timing latency is introduced.
// COPY FPS explicitly describes the placeholder copy path, not CNN inference.
module style_osd #(
    parameter integer IMAGE_WIDTH=640, IMAGE_Y=120, IMAGE_HEIGHT=480
)(
    input wire [15:0] x, y,
    input wire [15:0] capture_fps, process_fps,
    input wire [31:0] frame_id,
    input wire bypass_active,
    input wire [31:0] camera_frames, drop_count, error_count, underflow_count,
    output reg hit,
    output reg [23:0] rgb
);
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
                "I":glyph=35'b11111_00100_00100_00100_00100_00100_11111;
                "L":glyph=35'b10000_10000_10000_10000_10000_10000_11111;
                "M":glyph=35'b10001_11011_10101_10101_10001_10001_10001;
                "N":glyph=35'b10001_11001_11001_10101_10011_10011_10001;
                "O":glyph=35'b01110_10001_10001_10001_10001_10001_01110;
                "P":glyph=35'b11110_10001_10001_11110_10000_10000_10000;
                "R":glyph=35'b11110_10001_10001_11110_10100_10010_10001;
                "S":glyph=35'b01111_10000_10000_01110_00001_00001_11110;
                "T":glyph=35'b11111_00100_00100_00100_00100_00100_00100;
                "U":glyph=35'b10001_10001_10001_10001_10001_10001_01110;
                "V":glyph=35'b10001_10001_10001_10001_10001_01010_00100;
                "W":glyph=35'b10001_10001_10001_10101_10101_10101_01010;
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
                default:glyph=0;
            endcase
        end
    endfunction
    function [7:0] hex_char;
        input [3:0] value;
        begin hex_char=value<10 ? 8'd48+value : 8'd65+value-10; end
    endfunction
    function [7:0] decimal_char;
        input [15:0] value;
        input integer digit;
        reg [15:0] limited;
        begin
            limited=value>9999 ? 16'd9999 : value;
            case(digit)
                0:decimal_char=8'd48+(limited/1000)%10;
                1:decimal_char=8'd48+(limited/100)%10;
                2:decimal_char=8'd48+(limited/10)%10;
                default:decimal_char=8'd48+limited%10;
            endcase
        end
    endfunction
    integer local_x, local_y, index, col, row;
    reg [7:0] character;
    reg [34:0] bits;
    always @* begin
        local_x=0; local_y=0; index=0; col=0; row=0;
        character=" "; hit=0; rgb=24'hE0E0E0;
        if (y>=16 && y<30 && x>=8) begin
            local_y=y-16;
            if (x<8+8*12) begin
                local_x=x-8;
                case(local_x/12)
                    0:character="O"; 1:character="R"; 2:character="I"; 3:character="G";
                    4:character="I"; 5:character="N"; 6:character="A"; 7:character="L";
                endcase
                rgb=24'h60E0FF;
            end else if (x>=IMAGE_WIDTH+8 && x<IMAGE_WIDTH+8+6*12) begin
                local_x=x-IMAGE_WIDTH-8;
                case(local_x/12)
                    0:character="R"; 1:character="E"; 2:character="S";
                    3:character="U"; 4:character="L"; 5:character="T";
                endcase
                rgb=24'h80FF80;
            end
        end else if (y>=40 && y<54 && x>=8 && x<8+31*12) begin
            local_x=x-8; local_y=y-40; index=local_x/12;
            case(index)
                0:character="C"; 1:character="A"; 2:character="P";
                4:character="F"; 5:character="P"; 6:character="S"; 7:character=":";
                9,10,11,12:character=decimal_char(capture_fps,index-9);
                15:character="C"; 16:character="O"; 17:character="P"; 18:character="Y";
                20:character="F"; 21:character="P"; 22:character="S"; 23:character=":";
                25,26,27,28:character=decimal_char(process_fps,index-25);
            endcase
        end else if (y>=64 && y<78 && x>=8 && x<8+15*12) begin
            local_x=x-8; local_y=y-64; index=local_x/12;
            case(index)
                0:character="F"; 1:character="R"; 2:character="A";
                3:character="M"; 4:character="E"; 5:character=":";
                7,8,9,10,11,12,13,14:character=hex_char((frame_id >> ((14-index)*4)) & 4'hF);
            endcase
        end else if (y>=88 && y<102 && x>=8 && x<8+61*12) begin
            local_x=x-8; local_y=y-88; index=local_x/12;
            case(index)
                0:character="R"; 1:character="A"; 2:character="W"; 3:character=":";
                5,6,7,8,9,10,11,12:character=hex_char((camera_frames >> ((12-index)*4)) & 4'hF);
                16:character="D"; 17:character="R"; 18:character="O"; 19:character="P"; 20:character=":";
                22,23,24,25,26,27,28,29:character=hex_char((drop_count >> ((29-index)*4)) & 4'hF);
                33:character="E"; 34:character="R"; 35:character="R"; 36:character=":";
                38,39,40,41,42,43,44,45:character=hex_char((error_count >> ((45-index)*4)) & 4'hF);
                49:character="U"; 50:character="F"; 51:character=":";
                53,54,55,56,57,58,59,60:character=hex_char((underflow_count >> ((60-index)*4)) & 4'hF);
            endcase
        end else if (bypass_active && y>=IMAGE_Y+IMAGE_HEIGHT+24 &&
                     y<IMAGE_Y+IMAGE_HEIGHT+38 && x>=8 && x<8+11*12) begin
            local_x=x-8; local_y=y-(IMAGE_Y+IMAGE_HEIGHT+24); index=local_x/12;
            case(index)
                0:character="B"; 1:character="Y"; 2:character="P"; 3:character="A";
                4:character="S"; 5:character="S";
                7:character="C"; 8:character="O"; 9:character="P"; 10:character="Y";
            endcase
            rgb=24'hFFD060;
        end
        col=(local_x%12)/2; row=local_y/2;
        bits=glyph(character);
        if (col<5 && row<7) hit=bits[34-row*5-col];
    end
endmodule
