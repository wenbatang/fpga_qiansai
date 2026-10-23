"""Compile real freestanding RV32 firmware and generate learned weight catalog."""
from pathlib import Path
import hashlib,json,re,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2];BUILD=ROOT/'build/camera_ppi'
sys.path.append(str(WS/'pycode'))
from export_hardware import load_export,pack_taps
sys.path.append(str(WS/'xilinx/projects/uart_style_hdmi/scripts'))
from desktop_process import run
REF=WS/'elinx/elinxdemo/Ti60F225_DemoBoard_v4/10_Ti60f225_sc431hai2hdmi_demo/Ti60f225_sc431hai2hdmi_v7/Ti60f225_sc431hai2hdmi_v7'
TOOL=Path('E:/softare_FPGA/xpack-riscv-none-elf-gcc-15.2.0-1-win32-x64/xpack-riscv-none-elf-gcc-15.2.0-1/bin')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 BUILD.mkdir(parents=True,exist_ok=True)
 # Strip comments FIRST: the same ROM file contains a commented IMX219 table.
 p=REF/'rtl/cam_i2c_ctrl/i2c/i2c_master_reg_rom.v'
 text=re.sub(r'/\*.*?\*/|//[^\n]*','',p.read_text(encoding='utf-8',errors='replace'),flags=re.S)
 entries=[(int(i,16),int(a,16),int(v,16)) for i,a,v in re.findall(r"ROM\[8'h([0-9a-f]+)\]\s*=\s*\{16'h([0-9a-f]+),\s*8'h([0-9a-f]+)",text,re.I)]
 assert [i for i,a,v in entries]==list(range(164))
 # Hold standby through ALL trailing crop/mirror/exposure writes. Stream-on
 # moves to the very end of main(), after mode readback and weight loading.
 mode=[(a,v) for i,a,v in entries if not(a==0x0100 and v==1)]
 (BUILD/'camera_mode.h').write_text('/* Derived from V7 SC431HAI ROM; copyright notices retained in vendor source. */\n#include <stdint.h>\nstruct sensor_register {uint16_t address;uint8_t value;};\nstatic const struct sensor_register camera_mode[]={\n'+''.join('{0x%04x,0x%02x},\n'%x for x in mode)+'};\n#define CAMERA_MODE_COUNT 163\n')
 from model_catalog import catalog
 loaded,addresses,values=catalog();models=[meta for meta,_ in loaded]
 (BUILD/'style_catalog.h').write_text('#include <stdint.h>\nstatic const uint16_t style_addresses[1217]={'+','.join(map(str,addresses))+'};\nstatic const uint32_t style_values[4][1217]={'+','.join('{'+','.join(map(str,v))+'}' for v in values)+'};\n')
 command=[str(TOOL/'riscv-none-elf-gcc.exe'),'-march=rv32i_zicsr','-mabi=ilp32','-Os','-ffreestanding','-fno-builtin','-fno-pic','-msmall-data-limit=0','-nostdlib','-Wl,--no-relax','-Wl,-Map=firmware.map','-T',str(ROOT/'firmware/link.ld'),'-I',str(BUILD),str(ROOT/'firmware/start.S'),str(ROOT/'firmware/main.c'),'-lgcc','-o','firmware.elf']
 if run(command,BUILD,BUILD/'firmware_compile.log'):raise RuntimeError('Firmware compile failed')
 for fmt,out in [('ihex','firmware.hex'),('binary','firmware.bin')]:
  if run([str(TOOL/'riscv-none-elf-objcopy.exe'),'-O',fmt,'firmware.elf',out],BUILD,BUILD/(out+'.log')):raise RuntimeError('Objcopy failed')
 receipt={'isa':'RV32I_Zicsr, ILP32','ram_base':'0xf9000000','ram_bytes':32768,'apb_base':'0xf8100000','irq':16,'sensor_7bit_address':48,'sensor_id':'cd6b','mode_commands':len(mode),'mode_source':sha(p),'models':models,'weights_per_style':4536,'writes_per_style':1217,'firmware_bytes':(BUILD/'firmware.bin').stat().st_size,'files':{str(x.relative_to(WS)):sha(x) for x in [*sorted((ROOT/'firmware').glob('*')),BUILD/'camera_mode.h',BUILD/'style_catalog.h',BUILD/'firmware.elf',BUILD/'firmware.hex']}}
 (BUILD/'firmware_manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
 print('Compiled RV32 firmware:',receipt['firmware_bytes'],'bytes; four REAL learned styles; sensor ID/readback before streaming')
if __name__=='__main__':main()
