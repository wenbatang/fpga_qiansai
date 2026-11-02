"""Real Sapphire/current firmware: ten learned models, ROM byte lanes and IRQ."""
from pathlib import Path
import json,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simutil import config_file,questa,sha

def main():
    folder=ROOT/'sim/ten_sapphire';folder.mkdir(exist_ok=True);build=ROOT/'build/720p'
    for p in build.glob('Efx*.bin'):shutil.copy2(p,folder/p.name)
    assert len(list(folder.glob('Efx*.bin')))==4,'Four current boot byte lanes required'
    shutil.copy2(build/'weights.mem',folder/'weights.mem');assert len((folder/'weights.mem').read_text().split())==1840
    shutil.copy2(build/'ip/control_soc/Testbench/modelsim/control_soc.v',folder/'control_soc.v');config_file(folder/'config.mem',range(10))
    template=ROOT.parent/'camera_art_interactive/sim/sapphire/tb.sv';tb=template.read_text(encoding='utf-8')
    tb=tb.replace('expected[0:863]','expected[0:2159]')
    tb=tb.replace('.key_style(6\'d3)',".key_style(key_style),.gesture_event(1'b0),.gesture_style(6'd0)")
    tb=tb.replace('.psel(sel),.penable(en)', '.psel(sel && !gsel),.penable(en)')
    tb=tb.replace('.prdata(rd),.pready(ready),.pslverror(error)', '.prdata(ctrl_rd),.pready(ctrl_ready),.pslverror(ctrl_error)')
    extra='''
 wire gsel=(addr>='h80 && addr<='hbc) || (addr>='h2000 && addr<'h4000);
 wire[31:0]ctrl_rd;wire ctrl_ready,ctrl_error;reg[5:0]key_style=0;
 assign rd=gsel?32'd0:ctrl_rd;assign ready=gsel?1'b1:ctrl_ready;assign error=gsel?1'b0:ctrl_error;
 integer rom_reads=0,rom_byte_reads=0;reg midload_request_seen=0;
 always @(posedge clk)if(sel && en && !write && ready && addr>='h4000 && addr<'h5cc0)begin
  rom_reads<=rom_reads+1;if(addr[1:0]!=0)rom_byte_reads<=rom_byte_reads+1;
 end
'''
    tb=tb.replace(' control_soc cpu(',extra+'\n control_soc cpu(')
    tb=tb.replace('if(error)$fatal(1,"Sapphire emitted invalid APB write %h",addr);','if(error)$fatal(1,"Sapphire emitted invalid APB write %h",addr);')
    tb=tb.replace('wi<=wi+1;weight_writes<=weight_writes+1;', '''wi<=wi+1;weight_writes<=weight_writes+1;
   if(target==3 && wi==90)begin key<=1;key_style<=4;midload_request_seen<=1;end''')
    tb=tb.replace('if(starts==0)key<=1;', '''if(loaded!=starts)$fatal(1,"unexpected started model %0d expected%0d",loaded,starts);
   if(starts<9)begin key<=1;key_style<=starts+1;end''')
    tb=tb.replace('busy<=0;done<=1;', 'busy<=0;done<=1;if(starts==10)source_valid<=0;')
    start=tb.index('  if(starts>=2');end=tb.index('\n end\n initial begin',start)
    tb=tb[:start]+'''  if(starts==10 && irqs>=20 && !busy && !done && !irq)begin
   if(loaded!=9 || weight_writes!=2160 || sensor_writes!=167 || !midload_request_seen || rom_byte_reads==0)$fatal(1,"ten-model CPU acceptance loaded%0d writes%0d sensor%0d mid%0d bytes%0d",loaded,weight_writes,sensor_writes,midload_request_seen,rom_byte_reads);
   $display("PASS REAL Sapphire current firmware ten models/2160 learned payloads,ROM0x4000 byte-lane reads=%0d,total=%0d,mid-load target lock,START and PLIC W1C=%0d",rom_byte_reads,rom_reads,irqs);$finish;
  end'''+tb[end:]
    tb=tb.replace('#200000000;', '#400000000;').replace('Sapphire 200ms timeout','Sapphire 400ms timeout')
    (folder/'tb.sv').write_text(tb,encoding='utf-8')
    files=[folder/'control_soc.v',ROOT/'rtl/p720/video_control_apb_fast.sv',folder/'tb.sv']
    questa(folder,files,'tb_sapphire')
    bound=[*files,template,Path(__file__),ROOT/'scripts/simutil.py',folder/'config.mem',folder/'weights.mem',*list(folder.glob('*.bin')),build/'firmware.bin',*list((ROOT/'firmware').glob('*'))]
    for slot in range(10):bound.extend(next((ROOT/'parameters/c6').glob(f'{slot:02d}_*')).glob('*'))
    (folder/'verification.json').write_text(json.dumps(dict(result='PASS',styles=10,parameter_writes=2160,scope='Actual Sapphire RTL/current compiled firmware and ten learned models; SC431HAI I2C slave and busy/completion image engine modeled, hand capture disabled. No full SoC camera/frame/CNN or board acceptance',sources_sha256={str(p):sha(p) for p in dict.fromkeys(bound) if p.is_file()},logs_sha256={str(p):sha(p) for p in folder.glob('*.log')}),indent=2),encoding='utf-8')
if __name__=='__main__':main()
