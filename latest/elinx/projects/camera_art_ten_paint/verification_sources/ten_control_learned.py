"""Shared real-parameter APB regression, usable on RTL or actual EFX map."""
from pathlib import Path
import json,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simutil import config_file,questa,sha

def run_test(mapped=False):
    folder=ROOT/'sim'/('ten_control_mapped' if mapped else 'ten_control_learned');folder.mkdir(exist_ok=True)
    source=ROOT/'rtl/p720/video_control_apb_fast.sv';rom=ROOT/'build/720p/weights.mem'
    assert len(rom.read_text().split())==1840
    shutil.copy2(rom,folder/'weights.mem');config_file(folder/'config.mem',range(10))
    tb=r'''module tb;
reg clk=0;always #5 clk=~clk;reg reset=1;reg[15:0]addr=0;reg sel=0,en=0,wr=0;reg[31:0]wd=0;wire[31:0]rd;
wire ready,err,cv;wire[15:0]ca;wire[31:0]cd;wire weights;wire[5:0]loaded,requested;
reg busy=0,key=0;reg[5:0]key_style=0;reg[47:0]commands[0:2159];reg[31:0]rom[0:1839];
integer s,i,writes=0,mail_ticks=0;reg[31:0]value;wire mail_ready=mail_ticks==0;
video_control_apb_fast dut(.clk(clk),.reset(reset),.paddr(addr),.psel(sel),.penable(en),.pwrite(wr),.pwdata(wd),.prdata(rd),.pready(ready),.pslverror(err),.cfg_ready(mail_ready),.busy(busy),.source_valid(1'b1),.source_frame(32'd9),.engine_cycles(32'd0),.inference_frames(32'd0),.capture_frames(32'd1),.dropped_frames(32'd0),.completed(1'b0),.failed(1'b0),.camera_fault(1'b0),.key_event(key),.key_style(key_style),.gesture_event(1'b0),.gesture_style(6'd0),.scl_in(1'b1),.sda_in(1'b1),.cfg_valid(cv),.cfg_address(ca),.cfg_data(cd),.weights_valid(weights),.loaded_style(loaded),.requested_style(requested));
always @(posedge clk)begin
 if(reset)mail_ticks<=0;
 else if(cv)begin
  if(!mail_ready || writes>=2160 || {ca,cd}!==commands[writes])$fatal(1,"actual parameter payload/address mismatch #%0d a%h d%h",writes,ca,cd);
  writes=writes+1;mail_ticks<=4+(writes%9);
 end else if(mail_ticks>0)mail_ticks<=mail_ticks-1;
end
task access(input[15:0]a,input[31:0]d,input write_en,input expected_error);
begin @(negedge clk);sel=1;addr=a;wr=write_en;wd=d;en=0;@(negedge clk);en=1;#1;
while(!ready)begin @(negedge clk);#1;end
if(err!==expected_error)$fatal(1,"APB error a=%h d=%h err=%b",a,d,err);value=rd;@(negedge clk);sel=0;en=0;end endtask
initial begin
 $readmemh("weights.mem",rom);$readmemh("config.mem",commands);repeat(5)@(negedge clk);reset=0;
 for(i=0;i<1840;i=i+1)begin access('h4000+i*4,0,0,0);if(value!==rom[i])$fatal(1,"ROM word%0d actual%h expected%h",i,value,rom[i]);end
 access('h1000,0,0,1);access('h2000,0,0,1);access('h4001,0,0,0);if(value!==rom[0])$fatal(1,"byte lane ROM");access('h5cbf,0,0,0);if(value!==rom[1839])$fatal(1,"last byte ROM");access('h5cc0,0,0,1);access('h4000,0,1,1);
 for(s=0;s<10;s=s+1)begin
  access('h28,s,1,0);access('h2c,s,1,0);access('h30,2,1,0);
  access('h50,'h800,1,0);access('h54,5,1,1);access('h30,4,1,1);
  for(i=0;i<216;i=i+1)begin
   access('h50,commands[s*216+i][47:32],1,0);access('h54,commands[s*216+i][31:0],1,0);
   if(s==3 && i==100)begin key_style=9;key=1;@(negedge clk);key=0;end
  end
  access('h30,4,1,0);if(!weights || loaded!=s)$fatal(1,"load target changed during key request slot%0d loaded%0d",s,loaded);
  access('h54,0,1,1);busy=1;access('h30,2,1,1);if(!weights || loaded!=s)$fatal(1,"busy invalidated loaded parameters");busy=0;
 end
 if(writes!=2160)$fatal(1,"actual cfg writes count%0d",writes);
 $display("PASS actual ten models ROM1840words and2160 accepted parameter addresses/data, variable ACK wait, locked load target, illegal/partial/busy protection");$finish;
end
initial begin #10000000;$fatal(1,"timeout");end
endmodule'''
    (folder/'tb.sv').write_text(tb,encoding='utf-8')
    bound=[source,rom,folder/'weights.mem',folder/'config.mem',folder/'tb.sv',Path(__file__),ROOT/'scripts/simutil.py',ROOT/'sim'/('check_ten_control_mapped.py' if mapped else 'check_ten_control_learned.py')]
    for slot in range(10):bound.extend(next((ROOT/'parameters/c6').glob(f'{slot:02d}_*')).glob('*'))
    if mapped:
        probe=ROOT/'build/probe_ten_control';inputs=json.loads((probe/'inputs.json').read_text(encoding='utf-8'))
        for p,h in inputs.items():assert sha(Path(p))==h,'Stale control map input '+p
        mapped_source=probe/'outflow/video_control_apb_fast.map.v'
        files=[*sorted(Path('E:/software/efinity/sim_models/verilog').glob('*.v')),mapped_source,folder/'tb.sv']
        bound.extend([*files,probe/'inputs.json',*map(Path,inputs),probe/'map_console.log'])
    else:files=[folder/'tb.sv',source]
    questa(folder,files)
    (folder/'verification.json').write_text(json.dumps(dict(result='PASS',styles=10,rom_words=1840,accepted_parameter_transactions=2160,scope='Actual EFX RAM/logic mapping with all final learned parameters and RTL APB behavior' if mapped else 'Actual control RTL/all final learned parameters; no CPU or real camera/DDR',sources_sha256={str(p):sha(p) for p in dict.fromkeys(bound)},logs_sha256={str(p):sha(p) for p in folder.glob('*.log')}),indent=2),encoding='utf-8')
