// Pixel-domain diagnostic only. Inputs must be atomically frame-latched.
module style_wb_overlay(
    input wire [15:0] x,y,
    input wire [23:0] input_rgb,
    input wire [3:0] state,
    input wire [10:0] gain_r,gain_b,
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
                "J":glyph=35'b00111_00010_00010_00010_10010_10010_01100;
                "M":glyph=35'b10001_11011_10101_10101_10001_10001_10001;
                "U":glyph=35'b10001_10001_10001_10001_10001_10001_01110;
                "W":glyph=35'b10001_10001_10001_10101_10101_11011_10001;
                default:glyph=0;
            endcase
        end
    endfunction
    function [7:0] hex_char;
        input [3:0] nibble;
        begin hex_char=nibble<10 ? 8'd48+nibble : 8'd65+nibble-10; end
    endfunction

    reg [63:0] label;
    reg [7:0] ch;
    reg [34:0] dots;
    reg [87:0] heading;
    reg [159:0] help_text;
    integer lx,ly,index,col,row;
    always @* begin
        case(state)
            0:label="DEFAULT ";
            1,2:label="SAMPLE  ";
            3,4,8:label="CALC    ";
            5:label="APPLY   ";
            6:label="LOCKED  ";
            default:label="REJECT  ";
        endcase
        heading="WB CAL 01  ";help_text="  KEY2 CAL KEY3 RESET";
        rgb=input_rgb;ch=" ";dots=0;lx=0;ly=0;index=0;col=0;row=0;
        if(y>=628 && y<642 && x>=8 && x<8+52*12) begin
            lx=x-8;ly=y-628;index=lx/12;col=(lx%12)/2;row=ly/2;
            if(index<11) ch=heading >> ((10-index)*8);
            else if(index<19) ch=label >> ((18-index)*8);
            else case(index)
                19:ch="R";20:ch=":";
                21:ch=hex_char({1'b0,gain_r[10:8]});
                22:ch=hex_char(gain_r[7:4]);23:ch=hex_char(gain_r[3:0]);
                25:ch="B";26:ch=":";
                27:ch=hex_char({1'b0,gain_b[10:8]});
                28:ch=hex_char(gain_b[7:4]);29:ch=hex_char(gain_b[3:0]);
                default:if(index>=30 && index<50) ch=help_text >> ((49-index)*8);
            endcase
            dots=glyph(ch);
            rgb=24'h000000;
            if(col<5 && row<7 && dots[34-row*5-col])
                rgb=state==7?24'hFF8060:24'hFFFF80;
        end
        // Center RAW ROI outline, display-only, visible while collecting paper.
        if(state==1 || state==2) begin
            if(((x==298 || x==342) && y>=331 && y<=389) ||
               ((y==331 || y==389) && x>=298 && x<=342)) rgb=24'hFFFF00;
        end
    end
endmodule
