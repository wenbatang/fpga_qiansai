from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simutil import questa,receipt


def main():
    folder=ROOT/'sim/snapshot';folder.mkdir(exist_ok=True)
    tb=r'''module tb;
reg clk=0;always #5 clk=~clk;reg reset=1,enable=0,cancel=0,frame_start=0,frame_end=0,frame_bad=0,pixel_valid=0,learn_event=0,capture_event=0;
reg[31:0]pixels=0;reg[15:0]paddr=0;reg psel=0,penable=0,pwrite=0;reg[31:0]pwdata=0;
wire[31:0]prdata;wire selected,pslverror;wire[10:0]cpu_status;wire[255:0]diagnostics;wire guard_event;wire[5:0]guard_style;integer xx,yy,i,j,epoch1;reg[31:0]word;
gesture_snapshot dut(.*);
task tick;begin @(negedge clk);end endtask
task wr(input[15:0]a,input[31:0]v);begin psel=1;pwrite=1;paddr=a;pwdata=v;tick();penable=1;tick();psel=0;penable=0;pwrite=0;end endtask
task rd(input[15:0]a,output[31:0]v);begin psel=1;pwrite=0;paddr=a;tick();penable=1;#1;if(pslverror)$fatal(1,"read error");v=prdata;tick();psel=0;penable=0;end endtask
function[15:0]pattern(input integer x,input integer y);begin pattern=(x*131+y*251+16'h1357)&16'hffff;end endfunction
task frame(input integer bad,input integer invert);begin
 frame_start=1;tick();frame_start=0;
 for(yy=0;yy<720;yy=yy+1)for(xx=0;xx<1280;xx=xx+2)begin
  pixel_valid=1;pixels={16'hf81f,pattern((xx-4)/10,(yy-45)/10)^(invert?16'hffff:16'h0000)};tick();
 end
 pixel_valid=0;tick();frame_bad=bad;frame_end=1;tick();frame_end=0;frame_bad=0;tick();
end endtask
task check_image;begin
 for(i=0;i<2048;i=i+1)begin
  word={pattern((i*2+1)%64,(i*2+1)/64),pattern((i*2)%64,(i*2)/64)};
  rd(16'h2000+i*4,pwdata);if(pwdata!==word)$fatal(1,"RGB word%0d got%h expected%h",i,pwdata,word);
 end
end endtask
initial begin
 repeat(4)tick();reset=0;enable=1;tick();wr('h8c,1);frame(0,0);rd('h80,word);if(word[0]!==1)$fatal(1,"good frame not published");check_image();
 frame(0,1);check_image(); // CPU-owned snapshot cannot be overwritten.
 if(diagnostics[16:4]!=4096)$fatal(1,"held snapshot sample count changed");
 wr('h8c,2);wr('h8c,1);frame(1,1);rd('h80,word);if(word[0])$fatal(1,"bad frame published");
 wr('h8c,1);frame(0,0);rd('h88,word);epoch1=word;cancel=1;tick();cancel=0;rd('h80,word);if(word[0])$fatal(1,"manual change retained old snapshot");rd('h88,word);if(word==epoch1)$fatal(1,"cancel epoch missing");
 wr('h8c,1);enable=0;tick();rd('h80,word);if(word[2:0]!=0)$fatal(1,"disabled retained work");
 enable=1;tick();
 // A request in the very same ACCESS edge as SOF must start this frame.
 psel=1;pwrite=1;paddr='h8c;pwdata=1;tick();penable=1;frame_start=1;tick();
 psel=0;pwrite=0;penable=0;frame_start=0;rd('h80,word);if(!word[1])$fatal(1,"SOF-coincident request lost");
 wr('h8c,2);rd('h80,word);if(word[2:0]!=0)$fatal(1,"ACK did not cancel active");
 wr('ha0,32'h12345678);wr('ha4,32'h00030100);wr('ha8,32'h04000000);wr('hac,32'h030a0400);wr('hb0,32'h007b9a39);
 if(diagnostics[223:192]!=32'h12345678 || diagnostics[191:160]!=32'h00030100 || diagnostics[127:96]!=32'h030a0400 || diagnostics[95:64]!=32'h007b9a39)$fatal(1,"diagnostic mapping");
 wr('h90,32'hffffffff);rd('h90,word);if(word!==32'h000007ff || cpu_status!==11'h7ff)$fatal(1,"learning/ten-bit CPU status truncated");
 enable=0;learn_event=1;capture_event=1;tick();learn_event=0;capture_event=0;tick();
 rd('hb4,word);if(word!==3 || !cpu_status[10] || cpu_status[9:0]!=0)$fatal(1,"disabled lost learning state/commands");
 wr('hb4,1);rd('hb4,word);if(word!==2)$fatal(1,"W1C cleared wrong command");
 psel=1;pwrite=1;paddr='hb4;pwdata=3;tick();penable=1;learn_event=1;tick();learn_event=0;psel=0;penable=0;pwrite=0;tick();
 rd('hb4,word);if(word!==1)$fatal(1,"new event lost against W1C");
 repeat(50)tick();rd('hb4,word);if(word!==1)$fatal(1,"disabled command not retained");
 psel=1;pwrite=1;paddr='hb4;pwdata=4;tick();penable=1;#1;if(!pslverror)$fatal(1,"invalid command W1C mask accepted");tick();psel=0;penable=0;pwrite=0;
 rd('hb4,word);if(word!==1)$fatal(1,"invalid write changed pending command");wr('hb4,3);rd('hb4,word);if(word!==0)$fatal(1,"W1C clear failed");
 wr('h90,0);rd('h90,word);if(word!==0)$fatal(1,"disabled CPU could not exit learning");
 wr('h90,32'h7ff);rd('h90,word);if(word!==32'h400)$fatal(1,"disabled write lost learning or retained qualification");
 wr('h90,0);psel=1;pwrite=1;paddr='h90;pwdata='h400;tick();penable=1;cancel=1;learn_event=1;tick();
 psel=0;pwrite=0;penable=0;cancel=0;learn_event=0;rd('h90,word);if(word!=='h400)$fatal(1,"same-edge cancel lost new learning bit");
 wr('h90,0);rd('h90,word);if(word!==0)$fatal(1,"disabled CPU learning clear lost");
 reset=1;tick();reset=0;rd('hb4,word);if(word!=0 || cpu_status!=0)$fatal(1,"command/state reset");
 $display("PASS full720 ROI4096 RGB565 samples, all2048 color words, CPU ownership, bad EOF, mode/manual invalidation, request SOF, ACK cancel, diagnostics");$finish;
end
initial begin #50000000;$fatal(1,"timeout");end
endmodule'''
    (folder/'tb.sv').write_text(tb,encoding='utf-8');files=[folder/'tb.sv',ROOT/'rtl/gesture_snapshot.sv']
    questa(folder,files);receipt(folder,[*files,Path(__file__)],'Actual full720 color snapshot source/APB; all2048 words and green/grey/black colors retained. Artificial image stream, not real sensor accuracy')


if __name__=='__main__':main()
