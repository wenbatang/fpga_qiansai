// Compact 5x7 text: Cxx Ixx H60. C=DDR-published capture, I=CNN completed,
// H=nominal HDMI refresh. Position is associated with the registered RGB pixel.
module fps_overlay60(input wire[11:0] x,y,input wire[7:0] capture_fps,inference_fps,input wire[7:0]gesture,input wire[3:0]display_style,
 input wire enable,de,input wire[23:0] rgb,output wire[23:0] out_rgb);
 function automatic[34:0] glyph(input[4:0] code);
  begin case(code)
   0:glyph=35'b01110_10001_10011_10101_11001_10001_01110;
   1:glyph=35'b00100_01100_00100_00100_00100_00100_01110;
   2:glyph=35'b01110_10001_00001_00010_00100_01000_11111;
   3:glyph=35'b11110_00001_00001_01110_00001_00001_11110;
   4:glyph=35'b00010_00110_01010_10010_11111_00010_00010;
   5:glyph=35'b11111_10000_10000_11110_00001_00001_11110;
   6:glyph=35'b01110_10000_10000_11110_10001_10001_01110;
   7:glyph=35'b11111_00001_00010_00100_01000_01000_01000;
   8:glyph=35'b01110_10001_10001_01110_10001_10001_01110;
   9:glyph=35'b01110_10001_10001_01111_00001_00001_01110;
   10:glyph=35'b01111_10000_10000_10000_10000_10000_01111; // C
   11:glyph=35'b01110_00100_00100_00100_00100_00100_01110; // I
   12:glyph=35'b10001_10001_10001_11111_10001_10001_10001; // H
   13:glyph=35'b01110_10001_10000_10111_10001_10001_01110; // G
   14:glyph=35'b11110_10001_10001_11110_10000_10000_10000; // P
   16:glyph=35'b00000_00000_00000_11111_00000_00000_00000; // No candidate: dash, distinct from digit0.
   17:glyph=35'b01111_10000_10000_01110_00001_00001_11110; // S: committed front-buffer style.
   18:glyph=35'b10000_10000_10000_10000_10000_10000_11111; // L: learning label.
   19:glyph=35'b01110_10001_10001_11111_10001_10001_10001; // A: accepted learning samples.
   default:glyph=0;
  endcase end
 endfunction
 wire in_box=de && x>=16 && x<496 && y>=16 && y<44;
 wire[11:0] xx=x-16,yy=y-16;
 wire[4:0] ch=xx/24;
 wire[2:0] col=(xx%24)/4,row=yy/4;
 reg[4:0] code;
 reg[34:0] bits;
 always @* begin
  code=15;
  case(ch)
   0:code=10;1:code=capture_fps/10;2:code=capture_fps%10;
   4:code=11;5:code=inference_fps/10;6:code=inference_fps%10;
   8:code=12;9:code=6;10:code=0;
   // candidate_code1..10 maps to digit0..9;0/invalid maps to dash.
   12:code=gesture[7]?18:13;13:code=gesture[3:0]>=1 && gesture[3:0]<=10?{1'b0,gesture[3:0]}-1'b1:5'd16;
   15:code=gesture[7]?19:14;16:code={2'b00,gesture[6:4]};
   18:code=17;19:code=display_style<=9?{1'b0,display_style}:5'd16;
  endcase
  bits=glyph(code);
 end
 wire ink=col<5 && row<7 && bits[34-row*5-col];
 assign out_rgb=enable && in_box ? (ink ? 24'hffff00:24'h101010):rgb;
endmodule
