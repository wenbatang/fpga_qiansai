// Diagnostic-only RGB overlay. No clock, buffering or timing latency.
// Root feeds phase-0 RGB to both panes; the right pane swaps R/B (phase 3).
module style_color_probe_overlay #(
    parameter integer BOX_X0=299, BOX_X1=341,
    parameter integer BOX_Y0=332, BOX_Y1=388
)(
    input wire [15:0] x, y,
    input wire [23:0] input_rgb,
    input wire [39:0] cfa_means,
    input wire sample_valid,
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
                "L":glyph=35'b10000_10000_10000_10000_10000_10000_11111;
                "O":glyph=35'b01110_10001_10001_10001_10001_10001_01110;
                "P":glyph=35'b11110_10001_10001_11110_10000_10000_10000;
                "R":glyph=35'b11110_10001_10001_11110_10100_10010_10001;
                "T":glyph=35'b11111_00100_00100_00100_00100_00100_00100;
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
        input right_title;
        begin
            title_char=" ";
            if(!right_title) case(n)
                0:title_char="C";1:title_char="O";2:title_char="L";
                3:title_char="O";4:title_char="R";6:title_char="P";
                7:title_char="R";8:title_char="O";9:title_char="B";
                10:title_char="E";12:title_char="0";13:title_char="1";
                default:;
            endcase
            else case(n)
                0:title_char="L";1:title_char="E";2:title_char="F";
                3:title_char="T";5:title_char="0";7:title_char="R";
                8:title_char="I";9:title_char="G";10:title_char="H";
                11:title_char="T";13:title_char="3";
                default:;
            endcase
        end
    endfunction
    integer local_x,local_y,index,col,row,field_pos;
    reg [7:0] character;
    reg [9:0] mean;
    reg [34:0] dots;
    reg text_area;
    always @* begin
        rgb=input_rgb;
        local_x=0;local_y=0;index=0;col=0;row=0;field_pos=0;
        character=" ";mean=0;dots=0;text_area=0;
        // Only camera pixels are swapped. Footer and standard patches remain
        // independent references, including the blue patch crossing x=640.
        if(y>=120 && y<600 && x>=640 && x<1280)
            rgb={input_rgb[7:0],input_rgb[15:8],input_rgb[23:16]};
        if(y>=BOX_Y0 && y<=BOX_Y1 &&
           ((x>=BOX_X0 && x<=BOX_X1 &&
             (x==BOX_X0 || x==BOX_X1 || y==BOX_Y0 || y==BOX_Y1)) ||
            (x>=BOX_X0+640 && x<=BOX_X1+640 &&
             (x==BOX_X0+640 || x==BOX_X1+640 || y==BOX_Y0 || y==BOX_Y1))))
            rgb=24'hFFFF00;

        if(y>=644 && y<658) begin
            if(x>=8 && x<8+14*12) begin
                local_x=x-8;local_y=y-644;text_area=1;
                character=title_char(local_x/12,1'b0);
            end else if(x>=648 && x<648+14*12) begin
                local_x=x-648;local_y=y-644;text_area=1;
                character=title_char(local_x/12,1'b1);
            end
        end else if(y>=664 && y<678 && x>=8 && x<8+23*12) begin
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
        end
        col=(local_x%12)/2;row=local_y/2;dots=glyph(character);
        if(text_area && col<5 && row<7 && dots[34-row*5-col])
            rgb=24'hE0E0E0;

        if(y>=692 && y<712 && x<1280) case(x[10:8])
            0:rgb=24'hFF0000;
            1:rgb=24'h00FF00;
            2:rgb=24'h0000FF;
            3:rgb=24'hFFFFFF;
            default:rgb=24'h808080;
        endcase
    end
endmodule
