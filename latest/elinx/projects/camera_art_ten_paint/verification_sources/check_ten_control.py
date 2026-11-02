"""Actual ten-slot APB control/ROM boundaries, with synthetic ROM words only."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simutil import questa

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    folder=ROOT/'sim/ten_control';folder.mkdir(exist_ok=True)
    values=[(0x7b13579d^(i*0x01010307))&0xffffffff for i in range(1840)]
    (folder/'weights.mem').write_text(''.join(f'{v:08x}\n' for v in values),encoding='ascii')
    tb=r'''module tb;
reg clk=0;always #5 clk=~clk;
reg reset=1;reg[15:0]paddr=0;reg psel=0,penable=0,pwrite=0;reg[31:0]pwdata=0;
wire[31:0]prdata;wire pready,pslverror,irq;
reg cfg_ready=1,busy=0,source_valid=1;reg[31:0]source_frame=100,engine_cycles=0,inference_frames=0,capture_frames=0,dropped_frames=0;
reg completed=0,failed=0,camera_fault=0,key_event=0,gesture_event=0;reg[5:0]key_style=0,gesture_style=0;
reg scl_in=1,sda_in=1;wire capture_enable,sensor_reset_n,overlay_enable,scl_release,sda_release,start,cfg_valid;
wire[15:0]cfg_address;wire[31:0]cfg_data;wire weights_valid;wire[5:0]loaded_style,requested_style;
video_control_apb_fast dut(.*);
integer i,s,l,k,nw,nc,kind,total=0,starts=0,expected_writes=0;
reg[31:0]v;
always @(posedge clk)begin
 if(cfg_valid)total=total+1;
 if(start)starts=starts+1;
end
task tick;begin @(negedge clk);end endtask
task wr(input[15:0]a,input[31:0]d,input integer error_expected);begin
 psel=1;paddr=a;pwrite=1;pwdata=d;tick();penable=1;#1;
 while(!pready)begin tick();#1;end
 if(pslverror!==error_expected[0])$fatal(1,"write error a=%h data=%h got%0b",a,d,pslverror);
 tick();psel=0;penable=0;pwrite=0;tick();
end endtask
task rd(input[15:0]a,input integer error_expected,output[31:0]d);begin
 psel=1;paddr=a;pwrite=0;tick();penable=1;#1;
 if(!pready || pslverror!==error_expected[0])$fatal(1,"read error a=%h",a);
 d=prdata;tick();psel=0;penable=0;tick();
end endtask
task load(input integer slot);begin
 wr('h2c,slot,0);wr('h30,2,0);expected_writes=0;
 // An invalid parameter address must not advance config count.
 wr('h50,'hffff,0);wr('h54,0,1);rd('h58,0,v);if(v!=0)$fatal(1,"illegal cfg advanced count");
 for(l=0;l<10;l=l+1)begin
  nw=l==0 || l==9?20:(l%2?56:36);nc=l==9?3:6;
  for(k=0;k<nw;k=k+4)begin wr('h50,(l<<12)|k,0);wr('h54,(slot<<16)|k,0);expected_writes=expected_writes+1;end
  for(kind=1;kind<=2;kind=kind+1)for(k=0;k<nc;k=k+1)begin
   wr('h50,(l<<12)|(kind<<10)|k,0);wr('h54,kind==1?slot:8,0);expected_writes=expected_writes+1;
  end
 end
 rd('h58,0,v);if(v!=216 || expected_writes!=216)$fatal(1,"config count%0d/%0d",v,expected_writes);
 wr('h30,4,0);if(!weights_valid || loaded_style!=slot)$fatal(1,"wrong loaded style%0d/%0d",loaded_style,slot);
end endtask
initial begin
 repeat(4)tick();reset=0;tick();
 for(i=0;i<1840;i=i+1)begin rd('h4000+4*i,0,v);if(v!==(32'h7b13579d^(i*32'h01010307)))$fatal(1,"ROM[%0d]=%h",i,v);end
 rd('h1000,1,v);rd('h2000,1,v);rd('h3ffc,1,v);rd('h4001,0,v);if(v!=32'h7b13579d)$fatal(1,"ROM byte-lane read");rd('h5cc0,1,v);wr('h4000,0,1);
 for(s=0;s<10;s=s+1)begin
  wr('h28,s,0);rd('h28,0,v);if(v!=s)$fatal(1,"requested%0d/%0d",v,s);
  load(s);wr('h30,1,0);tick();
 end
 if(starts!=10 || total!=2160)$fatal(1,"starts/configs %0d/%0d",starts,total);
 wr('h28,10,0);rd('h28,0,v);if(v!=0)$fatal(1,"reservedID10 not default");
 key_style=9;key_event=1;tick();key_event=0;rd('h28,0,v);if(v!=9)$fatal(1,"keyID9 rejected");
 key_style=63;key_event=1;tick();key_event=0;rd('h28,0,v);if(v!=0)$fatal(1,"reserved keyID not default");
 // START and reload attempts during a running job must be refused.
 busy=1;wr('h30,1,1);wr('h30,2,1);wr('h2c,3,0);rd('h2c,0,v);if(v[5:0]!=9)$fatal(1,"busy changed loaded slot");busy=0;
 // Hold a cfg command under genuine APB wait states; no cfg pulse before ready.
 wr('h30,2,0);wr('h50,0,0);cfg_ready=0;psel=1;paddr='h54;pwdata=7;pwrite=1;tick();penable=1;
 repeat(4)begin #1;if(pready || cfg_valid)$fatal(1,"backpressure lost");tick();end
 cfg_ready=1;#1;if(!pready)$fatal(1,"never resumed");tick();psel=0;penable=0;pwrite=0;tick();
 rd('h58,0,v);if(v!=1)$fatal(1,"wait-state wrote more than once");
 $display("PASS ten valid style IDs,2160 parameter transactions,1840 ROM words, nonoverlap/alignment/permissions, busy protection, reserved fallback and APB wait");$finish;
end
initial begin #10000000;$fatal(1,"timeout");end
endmodule'''
    (folder/'tb.sv').write_text(tb,encoding='utf-8')
    files=[folder/'tb.sv',ROOT/'rtl/p720/video_control_apb_fast.sv']
    questa(folder,files)
    sources=[*files,folder/'weights.mem',Path(__file__),ROOT/'scripts/simutil.py']
    (folder/'verification.json').write_text(json.dumps(dict(result='PASS',styles=10,parameter_transactions=2160,rom_words=1840,scope='Actual control RTL; synthetic recognizable ROM and parameter payloads, no CNN numerical or real firmware/board proof',sources_sha256={str(p):sha(p) for p in sources},logs_sha256={str(p):sha(p) for p in folder.glob('*.log')}),indent=2),encoding='utf-8')

if __name__=='__main__':main()
