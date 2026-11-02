"""Run the real new RV32 image; camera/AXI/ROI are explicit MMIO models."""
from pathlib import Path
import hashlib,importlib.util,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(Path(__file__).parent))
from check_classifier import pose
from check_runtime import rgb_packed
from simutil import configs
source=ROOT.parent/'camera_art_styles/sim/check_firmware.py'
spec=importlib.util.spec_from_file_location('gesture_isa_base',source);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base);base.BUILD=ROOT/'build/720p'


class Bus(base.Bus):
    def __init__(self,digit,chinese=False,skin=0xa2c7):
        super().__init__();self.mask=rgb_packed(pose(digit,chinese),skin);self.ready=False;self.seq=0;self.steps=0;self.class_begin=None;self.report=None;self.irq_enabled=False
        self.rom=[int(v,16) for v in (ROOT/'build/720p/weights.mem').read_text().split()]
    def advance(self):
        self.steps+=1;self.now+=1000 if self.reg[0x60]!=3 else 1
    def read(self,address):
        if 0xf8100000<=address<0xf8110000:
            o=address-0xf8100000
            if o==0x80:return 8|int(self.ready)
            if o==0x84:return self.seq
            if o==0x88:return 1
            if 0x1000<=o<0x1b80:return self.rom[(o-0x1000)//4]
            if 0x2000<=o<0x4000:return int(self.mask[(o-0x2000)//4])
        return super().read(address)
    def write(self,address,value):
        if 0xf8100000<=address<0xf8110000:
            o=address-0xf8100000
            if o==0x30:
                if value&2:self.config={};self.reg[0x58]=0;self.reg[8]&=~8
                if value&4:
                    assert self.reg[0x58]==216 and self.config==dict(configs(self.slot));self.reg[0x2c]=64|self.slot;self.reg[8]|=8;self.loaded.append(self.slot)
                if value&1:self.reg[8]|=1;self.starts+=1
                return
            if o==0x8c:
                if value==1:self.ready=True;self.seq+=1
                if value==2:self.ready=False;self.class_begin=self.steps
                return
            if o==0x90:
                if value&128 and self.reg.get(0x94,0)>0:
                    self.report=dict(status=value,classification_instructions=self.steps-self.class_begin,seq=self.seq,diagnostics={f'{o:02x}':self.reg.get(o,0) for o in range(0xa0,0xb1,4)})
                return
            if o==0x94:self.reg[o]=value;return
            if 0xa0<=o<=0xb0 and o%4==0:self.reg[o]=value;return
        super().write(address,value)


class CPU(base.CPU):
    def read(self,address,size):
        if 0xf8100000<=address<0xf8110000:
            return (self.bus.read(address&~3)>>(8*(address&3)))&((1<<(size*8))-1)
        return super().read(address,size)


def main():
    records=[]
    for digit,chinese,skin in [(1,False,0xa2c7),(3,True,0x7cc7)]:
        bus=Bus(digit,chinese,skin);cpu=CPU(bus)
        for count in range(16000000):
            cpu.step()
            if bus.report:break
        assert bus.report and (bus.report['status']&7)==digit,(digit,bus.report,hex(cpu.pc))
        assert bus.loaded==[0] and bus.starts==1 and bus.sensor.reg.get(0x0100)==1
        verdict=bus.reg[0xa4];hits=bus.reg[0xa8];shape=bus.reg[0xac];mean=bus.reg[0xb0]
        assert bus.reg[0xa0]==1 and verdict&255==0 and (verdict>>16)&255==digit
        assert shape&65535 and (shape>>16)&255 and (shape>>24)&255==digit
        assert (verdict>>8)&255==(1 if skin==0x7cc7 else 0),(skin,hex(verdict))
        if skin==0x7cc7:
            assert hits&65535==0 and hits>>16>0,'Green hand must fail strict color and survive wide color'
            assert (mean>>8)&255>(mean>>16)&255,'The fixture must retain G>R after ROI averaging'
        records.append(dict(digit=digit,chinese=chinese,rgb565=f'{skin:04x}',**bus.report,steps=count+1));print(records[-1],flush=True)
    out=ROOT/'sim/rv32';out.mkdir(exist_ok=True)
    files=[Path(__file__),source,ROOT/'sim/check_runtime.py',ROOT/'sim/check_classifier.py',ROOT/'build/720p/firmware.bin',ROOT/'build/720p/weights.mem',*list((ROOT/'firmware').glob('*'))]
    result=dict(result='PASS',cases=records,scope='Actual RV32 machine code, complete sensor init/216 real parameter writes, RGB565 ROI segmentation and one classification/candidate report for ordinary/green synthetic hand colors; no full four-second Sapphire/SoC, real-user accuracy or cycles guarantee',sources_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__=='__main__':main()
