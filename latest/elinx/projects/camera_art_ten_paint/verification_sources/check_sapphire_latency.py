"""Actual Sapphire cycle probe of the new classifier, explicitly prepared state.

This standalone timing program is NOT the production boot image or an enrollment
acceptance test. Real firmware enrollment is tested independently with 58 ROIs.
"""
from pathlib import Path
import json,shutil,sys,re
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(WS/'pycode/gesture_digits/calibrated_reference'))
from simutil import run,questa,sha
from check_calibrated import frame
TOOL=Path('E:/softare_FPGA/xpack-riscv-none-elf-gcc-15.2.0-1-win32-x64/xpack-riscv-none-elf-gcc-15.2.0-1/bin')
def main():
 out=ROOT/'sim/sapphire_latency';out.mkdir(exist_ok=True)
 source=out/'latency.c';source.write_text('''#include <stdint.h>
#define REG(o) (*(volatile uint32_t *)(0xf8100000u+(o)))
#include "'''+(ROOT/'firmware/gesture_calibrated.c').as_posix()+'''"
void machine_trap(void){for(;;);}
int main(void){
 struct cal_metrics m;cal_reset();REG(0xe0)=10;
 for(unsigned n=0;n<3;n++)if(cal_capture_background(n))REG(0x60)=0xdead0001;
 REG(0xe0)=0;for(unsigned n=0;n<4;n++)if(cal_capture_template(0,n,&m))REG(0x60)=0xdead0002;
 /* Explicit BENCHMARK-ONLY initialization. It includes all 40 comparisons
  * while avoiding forty full enrollment captures in this cycle-only probe. */
 for(unsigned c=1;c<10;c++){
  cal_counts[c]=4;cal_limits[c]=40;
  for(unsigned p=0;p<4;p++)for(unsigned i=0;i<192;i++)cal_proto[c][p][i]=(uint8_t)(cal_proto[0][p][i]+90+c*11);
 }
 uint32_t before=REG(0x48);int id=cal_predict(&m);uint32_t cycles=REG(0x48)-before;
 REG(0xe8)=cycles;REG(0xec)=(uint32_t)id;REG(0x60)=0x600d0000;for(;;);
}
''',encoding='utf-8')
 assert run([str(TOOL/'riscv-none-elf-gcc.exe'),'-march=rv32im_zicsr','-mabi=ilp32','-Os','-ffreestanding','-fno-builtin','-msmall-data-limit=0','-nostdlib','-Wl,--no-relax','-T',str(ROOT/'firmware/link.ld'),str(ROOT/'firmware/start.S'),str(source),'-lgcc','-o','latency.elf'],out,out/'compile.log')==0
 assert run([str(TOOL/'riscv-none-elf-objcopy.exe'),'-O','binary','latency.elf','latency.bin'],out,out/'objcopy.log')==0
 data=(out/'latency.bin').read_bytes();image=data+bytes(32768-len(data));assert len(image)==32768
 for lane in range(4):
  name=f'EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol{lane}.bin'
  (out/name).write_text(''.join(f'{v:08b}\n' for v in image[lane::4]),encoding='ascii')
 soc=ROOT/'build/720p/ip/control_soc/Testbench/modelsim/control_soc.v';shutil.copy2(soc,out/'control_soc.v')
 (out/'pixels.mem').write_text(''.join(f'{int(v):08x}\n' for digit in [*range(10),None] for v in frame(digit)),encoding='ascii')
 tb=r'''`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;reg reset=1;wire[15:0]addr;wire sel,en,write;wire[31:0]wd;reg[31:0]rd;reg[31:0]timer=0,cost=0,id=32'hffffffff;integer image=10;
reg[31:0]pixels[0:22527];initial $readmemh("pixels.mem",pixels);
control_soc cpu(.io_systemClk(clk),.io_asyncReset(reset),.io_systemReset(),.jtagCtrl_enable(1'b0),.jtagCtrl_tdi(1'b0),.jtagCtrl_capture(1'b0),.jtagCtrl_shift(1'b0),.jtagCtrl_update(1'b0),.jtagCtrl_reset(1'b1),.jtagCtrl_tck(1'b0),.userInterruptA(1'b0),.io_apbSlave_0_PADDR(addr),.io_apbSlave_0_PSEL(sel),.io_apbSlave_0_PENABLE(en),.io_apbSlave_0_PWRITE(write),.io_apbSlave_0_PWDATA(wd),.io_apbSlave_0_PRDATA(rd),.io_apbSlave_0_PREADY(1'b1),.io_apbSlave_0_PSLVERROR(1'b0));
always @*begin rd=0;if(addr=='h48)rd=timer;else if(addr>='h2000 && addr<'h4000)rd=pixels[image*2048+((addr-'h2000)>>2)];end
always @(posedge clk)begin
 timer<=timer+1;
 if(sel && en && write)case(addr)
  'he0:image<=wd;
  'he8:cost<=wd;
  'hec:id<=wd;
  'h60:begin
   if(wd!=32'h600d0000)$fatal(1,"benchmark setup failed %h",wd);
   if(id!=0 || cost==0 || cost>=33300000)$fatal(1,"classifier deadline/id failed %0d/%0d",cost,id);
   $display("PASS actual Sapphire enhanced classification_cycles=%0d",cost);$finish;
  end
 endcase
end
initial begin #200;reset=0;#600000000;$fatal(1,"cycle probe timeout");end
endmodule'''
 (out/'tb.sv').write_text(tb,encoding='utf-8');questa(out,[out/'control_soc.v',out/'tb.sv'])
 log=(out/'vsim.log').read_text(encoding='utf-8');cycles=int(re.search(r'classification_cycles=(\d+)',log)[1])
 files=[Path(__file__),source,ROOT/'firmware/gesture_calibrated.c',ROOT/'firmware/start.S',ROOT/'firmware/link.ld',soc,*out.glob('*.bin'),out/'pixels.mem',out/'tb.sv']
 receipt=dict(result='PASS',classification_ui_cycles=cycles,clock_hz=100000000,classification_ms=cycles/100000,
  sources_sha256={str(p):sha(p) for p in files},logs_sha256={str(p):sha(p) for p in out.glob('*.log')},
  scope='Actual Sapphire cycle measurement for one synthetic fist; standalone timing firmware prepares other-class prototypes explicitly. Not production boot/enrollment proof, worst-case latency, real-camera accuracy or board FPS.')
 (out/'verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(receipt['classification_ms'])
if __name__=='__main__':main()
