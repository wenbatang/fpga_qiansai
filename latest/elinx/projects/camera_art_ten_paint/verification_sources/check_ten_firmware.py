"""Actual RV32 firmware control of all ten learned styles; hand capture disabled."""
from pathlib import Path
import importlib.util,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simutil import configs,sha
from riscv_m import with_m
ISA=ROOT.parent/'camera_art_styles/sim/check_firmware.py'
spec=importlib.util.spec_from_file_location('ten_control_isa',ISA);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
base.BUILD=ROOT/'build/720p'

class Bus(base.Bus):
    def __init__(self,bad_id=False):
        super().__init__(bad_id);self.instructions=0;self.busy_until=0;self.key_at=0;self.key_injected=False;self.completed=0
        self.cfg_log=[];self.start_slots=[];self.committed=[];self.command_sets=[configs(i) for i in range(10)]
        self.rom=[int(v,16) for v in (ROOT/'build/720p/weights.mem').read_text().split()];assert len(self.rom)==1840
    def read(self,address):
        if 0xf8100000<=address<0xf8110000:
            o=address-0xf8100000
            if 0x4000<=o<0x5cc0:return self.rom[(o-0x4000)//4]
            if o==0x80:return 0 # Explicit model: recognition not enabled here.
            if o in (0x84,0x88,0xb4):return 0
        return super().read(address)
    def request(self,slot):
        self.reg[0x28]=slot;self.reg[0xc]|=8
    def write(self,address,value):
        if 0xf8100000<=address<0xf8110000:
            o=address-0xf8100000
            if o==0x28:self.reg[o]=value if value<10 else 0;return
            if o==0x2c:
                assert not self.reg[8]&1;self.slot=value if value<10 else 0;return
            if o==0x54:
                assert not self.reg[8]&9,'Parameter written while busy/weights valid'
                n=self.reg[0x58];assert n<216 and (self.reg[0x50],value)==self.command_sets[self.slot][n]
                self.config[self.reg[0x50]]=value;self.reg[0x58]+=1;self.cfg_log.append([self.slot,self.reg[0x50],value])
                if self.slot==3 and self.reg[0x58]==90:
                    self.request(4);self.key_injected=True
                return
            if o==0x30:
                if value&2:self.config={};self.reg[0x58]=0;self.reg[8]&=~8
                if value&4:
                    assert self.reg[0x58]==216 and self.config==dict(self.command_sets[self.slot])
                    self.reg[0x2c]=64|self.slot;self.reg[8]|=8;self.loaded.append(self.slot);self.committed.append(self.slot)
                if value&1:
                    assert self.reg[8]&8 and not self.reg[8]&1 and self.slot==self.starts
                    self.reg[8]|=1;self.starts+=1;self.start_slots.append(self.slot);self.busy_until=self.now+800;self.key_at=self.now+40
                return
            if o in (0x8c,0x90,0x94,0xa0,0xa4,0xa8,0xac,0xb0):self.reg[o]=value;return
        super().write(address,value)
    def advance(self):
        self.instructions+=1;self.now+=1000 if self.reg[0x60]!=3 else 1
        if self.key_at and self.now>=self.key_at:
            self.key_at=0
            if self.starts<10:self.request(self.starts)
        if self.busy_until and self.now>=self.busy_until:
            self.busy_until=0;self.reg[8]&=~1;self.reg[0xc]|=1;self.completed+=1
            if self.completed==10:self.reg[8]&=~4

class CPU(with_m(base.CPU)):
    def read(self,address,size):
        if 0xf8100000<=address<0xf8110000:
            return (self.bus.read(address&~3)>>(8*(address&3)))&((1<<(size*8))-1)
        return super().read(address,size)

def scenario(bad_id=False,missing_m=False):
    bus=Bus(bad_id);cpu=CPU(bus)
    if missing_m:cpu.csr[0x301]&=~(1<<12)
    for count in range(3000000):
        cpu.step()
        if (bad_id or missing_m) and bus.reg[0x60]==(0x80000070 if missing_m else 0x80000003) and bus.reg[4]==4 and bus.sensor.lines==3:break
        if not bad_id and not missing_m and bus.completed==10 and bus.reg[0xc]==0:break
    else:raise AssertionError(('Firmware control deadline',bus.loaded,bus.starts,hex(cpu.pc),bus.reg))
    if bad_id or missing_m:
        assert not bus.loaded and not bus.sensor.writes and bus.sensor.lines==3
        if missing_m:assert cpu.m_instructions==0
    else:
        assert bus.loaded==list(range(10)) and bus.start_slots==list(range(10)) and len(bus.cfg_log)==2160
        assert bus.key_injected and bus.traps>=10 and bus.reg[0x60]==3
        assert len(bus.sensor.writes)==167 and bus.sensor.writes[-1]==(0x0100,1)
        assert cpu.m_instructions>=2,'MUL/DIV self-test did not run'
    return dict(wrong_id=bad_id,missing_m=missing_m,instructions=count+1,m_instructions=cpu.m_instructions,loaded=bus.loaded,starts=bus.start_slots,completed=bus.completed,interrupts=bus.traps,parameter_writes=len(bus.cfg_log),midload_request_injected=bus.key_injected)

def main():
    out=ROOT/'sim/ten_firmware';out.mkdir(exist_ok=True)
    results=[scenario(False),scenario(True),scenario(False,True)]
    files=[Path(__file__),ISA,ROOT/'sim/riscv_m.py',ROOT/'scripts/simutil.py',ROOT/'build/720p/firmware.bin',ROOT/'build/720p/weights.mem',*list((ROOT/'firmware').glob('*'))]
    for i in range(10):files.extend(next((ROOT/'parameters/c6').glob(f'{i:02d}_*')).glob('*'))
    value=dict(result='PASS',tests=results,scope='Actual compiled RV32 machine code/I2C/2160 actual learned parameter writes/ten targets/IRQ; hand capture disabled and image engine modeled, not Sapphire cycles or board',sources_sha256={str(p):sha(p) for p in files if p.is_file()})
    (out/'verification.json').write_text(json.dumps(value,indent=2),encoding='utf-8');print(json.dumps(value['tests'],indent=2))
if __name__=='__main__':main()
