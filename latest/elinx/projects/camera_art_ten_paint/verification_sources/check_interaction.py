"""Ten-slot keys, true committed style display, atomic GP/S mailbox and glyphs."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simutil import questa
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    folder=ROOT/'sim/interaction';folder.mkdir(exist_ok=True)
    production=ROOT/'rtl/p720/video_system_720.sv';source=production.read_text(encoding='utf-8')
    begin=source.index(' always @(posedge clk)begin',source.index('// Only completed neural jobs count'))
    end=source.index(' assign inference_frames=neural_frames;',begin)
    declarations="""module frame_state(input wire clk,reset,engine_start,engine_done,engine_raw,commit_ack,commit_raw,
input wire[1:0]display_mode,output_bank,commit_bank,input wire[5:0]loaded_style,
output reg[31:0]neural_frames,output reg front_raw,output reg[1:0]front_mode,output reg[3:0]front_style);
reg[1:0]job_mode,bank_modes[0:2];reg[3:0]job_style,bank_styles[0:2];integer mode_index;
"""
    extracted=folder/'frame_state.sv';extracted.write_text(declarations+source[begin:end]+'endmodule\n',encoding='utf-8')
    tb=r'''module tb;
reg clk=0,pixel_clk=0;always #5 clk=~clk;always #7 pixel_clk=~pixel_clk;
reg reset=1,pixel_reset=1,learning_active=0,gesture_confirm=0;wire ui_visible;reg[3:0]keys_n=15,current_style=0;
wire event_valid,raw_mode,split_mode,learn_event,capture_event,mode_event;wire[5:0]event_style;wire[1:0]key_display;integer learns=0,captures=0;
style_keys47 #(.DEBOUNCE_CYCLES(3),.LEARN_HOLD_CYCLES(20)) keys(.clk(clk),.reset(reset),.keys_n(keys_n),.current_style(current_style),.learning_active(learning_active),.gesture_confirm(gesture_confirm),.ui_visible(ui_visible),.learn_event(learn_event),.capture_event(capture_event),.mode_event(mode_event),.event_valid(event_valid),.event_style(event_style),.raw_mode(raw_mode),.display_mode(key_display),.split_mode(split_mode));
always @(posedge clk)if(!reset && event_valid)current_style<=event_style[3:0];
always @(posedge clk)begin if(learn_event)learns=learns+1;if(capture_event)captures=captures+1;end
reg[31:0]captured=0,inferred=0;reg vblank=0;reg[7:0]gesture_status=0;wire[7:0]capture_fps,inference_fps;wire[7:0]gesture_pixel;wire[3:0]display_style;
reg frame_valid=0;wire[3:0]front_style;wire[1:0]front_mode;wire front_raw;wire[31:0]neural_frames;
reg engine_start=0,engine_done=0,engine_raw=1,commit_ack=0,commit_raw=1;
reg[1:0]display_mode=0,output_bank=0,commit_bank=0;reg[5:0]loaded_style=0;
frame_state state(.*);
fps_snapshot #(.CLOCK_HZ(20)) fps(.clk(clk),.reset(reset),.captured(captured),.inferred(inferred),.pixel_clk(pixel_clk),.pixel_reset(pixel_reset),.vblank(vblank),.gesture_status(gesture_status),.front_style(frame_valid?front_style:4'hf),.capture_fps(capture_fps),.inference_fps(inference_fps),.gesture_pixel(gesture_pixel),.display_style(display_style));
task tick(input integer n);begin repeat(n)@(negedge clk);end endtask
task press(input integer n);begin keys_n=15^(1<<n);tick(12);keys_n=15;tick(12);end endtask
reg[11:0]x=0,y=0;reg[7:0]og=0;reg[3:0]os=15;wire[23:0]screen;reg[34:0]digits[0:9],dash;integer d,r,c,s,m,k=0,neural=0,previous_mode=0,previous_style=0,glyph_checks=0;
fps_overlay60 overlay(.x(x),.y(y),.capture_fps(8'd30),.inference_fps(8'd20),.gesture(og),.display_style(os),.enable(1'b1),.de(1'b1),.rgb(24'h123456),.out_rgb(screen));
task glyph_check(input integer ch,input[34:0]bits);
begin
 for(r=0;r<7;r=r+1)for(c=0;c<5;c=c+1)begin
  x=16+ch*24+c*4;y=16+r*4;#1;
  if(screen!==(bits[34-r*5-c]?24'hffff00:24'h101010))$fatal(1,"glyph ch%0d pixel%0d/%0d got%h",ch,r,c,screen);
  glyph_checks=glyph_checks+1;
 end
end endtask
initial begin
 tick(4);reset=0;pixel_reset=0;tick(12);
 for(s=0;s<10;s=s+1)begin current_style=s;press(1);if(current_style!=(s+1)%10)$fatal(1,"next slot %0d got%0d",s,current_style);end
 for(s=0;s<10;s=s+1)begin current_style=s;press(2);if(current_style!=(s+9)%10)$fatal(1,"previous slot %0d got%0d",s,current_style);end
 press(0);if(key_display!=1)$fatal(1,"STYLE");press(0);if(!split_mode)$fatal(1,"SPLIT");press(0);if(!raw_mode)$fatal(1,"RAW");
 keys_n=9;tick(12);keys_n=15;tick(12);if(learns!=0)$fatal(1,"short chord entered learning");
 press(0);if(key_display!=1)$fatal(1,"STYLE before learning");keys_n=9;tick(60);if(learns!=1 || key_display!=0)$fatal(1,"learning chord/forced RAW");
 tick(60);if(learns!=1)$fatal(1,"held chord repeated");
 keys_n=15;tick(1);keys_n=9;tick(60);if(learns!=1)$fatal(1,"undebounced glitch rearmed long chord");
 keys_n=15;tick(12);learning_active=1;
 press(0);if(captures!=1 || key_display!=0)$fatal(1,"learning KEY0 changed view instead of capture");
 current_style=9;press(1);if(current_style!=0)$fatal(1,"learning next label");press(2);if(current_style!=9)$fatal(1,"learning previous label");
 keys_n=9;tick(60);if(learns!=2)$fatal(1,"learning exit chord missing");keys_n=15;tick(12);learning_active=0;
 press(0);if(key_display!=1 || captures!=1)$fatal(1,"normal keys not restored");
 if(!ui_visible)$fatal(1,"UI defaults hidden");
 press(3);if(ui_visible)$fatal(1,"KEY3 did not hide UI");
 keys_n=7;tick(200);if(!ui_visible)$fatal(1,"second KEY3 press did not show UI");
 tick(200);if(!ui_visible)$fatal(1,"held KEY3 repeatedly toggled");keys_n=15;tick(12);
 press(0);if(key_display!=2)$fatal(1,"SPLIT before gesture");
 gesture_confirm=1;tick(1);gesture_confirm=0;tick(1);if(key_display!=2)$fatal(1,"gesture changed SPLIT");
 press(0);if(key_display!=0)$fatal(1,"RAW before gesture");
 gesture_confirm=1;tick(1);gesture_confirm=0;tick(1);if(key_display!=1)$fatal(1,"RAW accepted gesture did not auto STYLE");
 vblank=1;tick(60);if(display_style!=15)$fatal(1,"invalid front should show S-");
 // Compile the actual production metadata block. New requested/loaded IDs
 // must not appear as S before final job completion and reader commit ACK.
 for(m=0;m<3;m=m+1)for(s=0;s<10;s=s+1)begin
  display_mode=m;loaded_style=s;output_bank=k%3;engine_raw=m==0;engine_start=1;tick(1);engine_start=0;
  display_mode=(m+1)%3;loaded_style=(s+1)%10;tick(65);
  if(front_mode!=previous_mode || front_style!=previous_style)$fatal(1,"busy request changed front metadata");
  if(frame_valid && display_style!=previous_style)$fatal(1,"S showed requested style before completion");
  engine_done=1;tick(1);engine_done=0;if(m!=0)neural=neural+1;
  if(neural_frames!=neural)$fatal(1,"RAW incorrectly counted as inference");
  tick(65);if(front_style!=previous_style || (frame_valid && display_style!=previous_style))$fatal(1,"S changed before safe ACK");
  commit_bank=k%3;commit_raw=m==0;commit_ack=1;tick(1);commit_ack=0;frame_valid=1;
  if(front_mode!=m || front_style!=s || front_raw!=(m==0))$fatal(1,"committed metadata mismatch");
  tick(65);if(display_style!=s)$fatal(1,"S mailbox lost committed style%0d got%0d",s,display_style);
  previous_mode=m;previous_style=s;k=k+1;
 end
 gesture_status={1'b1,3'd4,4'd10};captured=30;inferred=20;tick(60);
 if(gesture_pixel!={1'b1,3'd4,4'd10})$fatal(1,"ten-digit learning gesture mailbox");
 vblank=0;gesture_status=0;tick(60);if(gesture_pixel!={1'b1,3'd4,4'd10})$fatal(1,"bundle changed outside vblank");
 vblank=1;tick(60);if(gesture_pixel!=0)$fatal(1,"bundle did not refresh after ACK");
 digits[0]=35'b01110_10001_10011_10101_11001_10001_01110;
 digits[1]=35'b00100_01100_00100_00100_00100_00100_01110;
 digits[2]=35'b01110_10001_00001_00010_00100_01000_11111;
 digits[3]=35'b11110_00001_00001_01110_00001_00001_11110;
 digits[4]=35'b00010_00110_01010_10010_11111_00010_00010;
 digits[5]=35'b11111_10000_10000_11110_00001_00001_11110;
 digits[6]=35'b01110_10000_10000_11110_10001_10001_01110;
 digits[7]=35'b11111_00001_00010_00100_01000_01000_01000;
 digits[8]=35'b01110_10001_10001_01110_10001_10001_01110;
 digits[9]=35'b01110_10001_10001_01111_00001_00001_01110;
 dash=35'b00000_00000_00000_11111_00000_00000_00000;
 for(d=0;d<=4;d=d+1)begin og={d[2:0],4'd10};glyph_check(16,digits[d]);end
 for(d=0;d<16;d=d+1)begin og={3'd4,d[3:0]};if(d>=1 && d<=10)glyph_check(13,digits[d-1]);else glyph_check(13,dash);end
 for(d=0;d<=9;d=d+1)begin os=d;glyph_check(19,digits[d]);end
 os=15;glyph_check(19,dash);
 og=8'h80;glyph_check(12,35'b10000_10000_10000_10000_10000_10000_11111);glyph_check(15,35'b01110_10001_10001_11111_10001_10001_10001);
 reset=1;tick(1);if(front_style!=0 || front_mode!=0 || !front_raw || neural_frames!=0)$fatal(1,"reset metadata");
 $display("PASS ten-slot keys,30 actual production RAW/STYLE/SPLIT metadata cases, S only after safe ACK, stable GP/S mailbox and%0d glyph pixels",glyph_checks);$finish;
end
endmodule'''
    (folder/'tb.sv').write_text(tb,encoding='utf-8')
    files=[folder/'tb.sv',extracted,ROOT/'rtl/style_keys47.sv',ROOT/'rtl/fps_snapshot.sv',ROOT/'rtl/hdmi60/fps_overlay60.sv']
    questa(folder,files)
    bound=[*files,production,Path(__file__),ROOT/'scripts/simutil.py']
    (folder/'verification.json').write_text(json.dumps(dict(result='PASS',metadata_cases=30,glyph_pixels=1190,scope='Actual keys/optional calibration chord/capture/mailbox/overlay RTL and literal production metadata block; completion/reader ACK modeled, not full system or actual DDR',sources_sha256={str(p):sha(p) for p in bound},logs_sha256={str(p):sha(p) for p in folder.glob('*.log')}),indent=2),encoding='utf-8')
if __name__=='__main__':main()
