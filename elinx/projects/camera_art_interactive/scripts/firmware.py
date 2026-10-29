"""Compile RV32 control and refresh all four boot RAM lanes of this copied SoC."""
from pathlib import Path
import sys,hashlib,json
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'build/720p'
sys.path.insert(0,str(Path(__file__).parent));from desktop_process import run
TOOL=Path('E:/softare_FPGA/xpack-riscv-none-elf-gcc-15.2.0-1-win32-x64/xpack-riscv-none-elf-gcc-15.2.0-1/bin')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    command=[str(TOOL/'riscv-none-elf-gcc.exe'),'-march=rv32i_zicsr','-mabi=ilp32','-Os','-ffreestanding','-fno-builtin','-fno-pic','-msmall-data-limit=0','-nostdlib','-Wl,--no-relax','-Wl,-Map=firmware.map','-T',str(ROOT/'firmware/link.ld'),'-I',str(B),str(ROOT/'firmware/start.S'),str(ROOT/'firmware/main.c'),'-lgcc','-o','firmware.elf']
    assert run(command,B,B/'firmware_compile.log')==0
    for fmt,name in [('binary','firmware.bin'),('ihex','firmware.hex')]:assert run([str(TOOL/'riscv-none-elf-objcopy.exe'),'-O',fmt,'firmware.elf',name],B,B/(name+'.log'))==0
    data=(B/'firmware.bin').read_bytes();assert len(data)<32768-2048
    image=data+bytes(32768-len(data));lanes={}
    for lane in range(4):
        name=f'EfxSapphireSoc.v_toplevel_system_ramA_logic_ram_symbol{lane}.bin';text=''.join(f'{value:08b}\n' for value in image[lane::4])
        for directory in [B,B/'ip/control_soc']:(directory/name).write_text(text,encoding='ascii')
        lanes[name]=sha(B/name)
    result=dict(result='PASS',firmware_bytes=len(data),ram_bytes=32768,styles=4,config_writes_per_style=216,weights_rom_bytes=2944,firmware_sha256=sha(B/'firmware.bin'),lanes=lanes,files={str(p):sha(p) for p in (ROOT/'firmware').glob('*') if p.is_file()})
    (B/'firmware_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('FIRMWARE',len(data),'bytes; all four boot lanes updated')
if __name__=='__main__':main()
