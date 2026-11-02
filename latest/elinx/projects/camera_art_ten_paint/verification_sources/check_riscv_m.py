"""RV32M arithmetic edge cases and IRQ/bus-advance adapter behavior."""
from pathlib import Path
import hashlib,json,random
from riscv_m import multiply_divide,with_m
ROOT=Path(__file__).resolve().parents[1]
def reference(a,b,f):
    sa=a if a<2**31 else a-2**32;sb=b if b<2**31 else b-2**32
    if f<4:return [(a*b)&0xffffffff,((sa*sb)>>32)&0xffffffff,((sa*b)>>32)&0xffffffff,((a*b)>>32)&0xffffffff][f]
    if f in (4,6):
        q=-1 if not b else (-2**31 if sa==-2**31 and sb==-1 else (abs(sa)//abs(sb))*(-1 if (sa<0)^(sb<0) else 1))
        return (q if f==4 else (sa if not b else sa-q*sb))&0xffffffff
    return (0xffffffff if not b else a//b) if f==5 else (a if not b else a%b)
def main():
    random.seed(20261101);values=[0,1,2,7,0x7fffffff,0x80000000,0xffffffff,0xfffffff9]
    cases=[(a,b,f) for a in values for b in values for f in range(8)]
    cases += [(random.getrandbits(32),random.getrandbits(32),f) for f in range(8) for _ in range(2000)]
    for a,b,f in cases:assert multiply_divide(a,b,f)==reference(a,b,f),(a,b,f)
    class Bus:
        def __init__(self):self.reg={0xc:0,0x10:0};self.traps=0;self.ticks=0
        def advance(self):self.ticks+=1
    class Base:
        def __init__(self):self.bus=Bus();self.csr={0x300:0,0x304:0,0x305:0,0x341:0,0x342:0};self.r=[0]*32;self.pc=0;self.words={}
        def read(self,a,size):return self.words[a]
        def step(self):self.bus.advance();assert self.read(self.pc,4)==0x13;self.pc+=4
    CPU=with_m(Base);cpu=CPU();cpu.r[1]=0xfffffff9;cpu.r[2]=9
    cpu.words[0]=(1<<25)|(2<<20)|(1<<15)|(3<<7)|0x33;cpu.step()
    assert cpu.r[3]==0xffffffc1 and cpu.pc==4 and cpu.bus.ticks==1 and cpu.m_instructions==1
    cpu.words[4]=0x13;cpu.step();assert cpu.pc==8 and cpu.bus.ticks==2
    cpu.csr.update({0x300:8,0x304:0x800,0x305:0x100});cpu.bus.reg.update({0xc:1,0x10:1});cpu.words[0x100]=0x13
    cpu.step();assert cpu.pc==0x104 and cpu.bus.traps==1 and cpu.bus.ticks==3 and cpu.csr[0x341]==8
    files=[Path(__file__),ROOT/'sim/riscv_m.py',ROOT/'build/720p/ip/control_soc/control_soc.v']
    out=ROOT/'sim/riscv_m';out.mkdir(exist_ok=True)
    result=dict(result='PASS',arithmetic_cases=len(cases),irq_and_advance_cases=3,scope='Python ISA adapter arithmetic and event accounting; real Sapphire verification is separate',sources_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('PASS RV32M',len(cases),'arithmetic cases and3event tests')
if __name__=='__main__':main()
