"""RV32M extension of the existing read-only ISA test model, not hardware RTL.

The real copied Sapphire already has MulPlugin/DivPlugin and misa=0x40001101.
This adapter advances the modeled bus exactly once and preserves IRQ entry.
"""
def signed(value):
    value&=0xffffffff
    return value-0x100000000 if value&0x80000000 else value

def multiply_divide(a,b,funct3):
    a&=0xffffffff;b&=0xffffffff;sa,sb=signed(a),signed(b)
    if funct3==0:value=a*b
    elif funct3==1:value=(sa*sb)>>32
    elif funct3==2:value=(sa*b)>>32
    elif funct3==3:value=(a*b)>>32
    elif funct3 in (4,6):
        if sb==0:q=-1;r=sa
        elif sa==-2147483648 and sb==-1:q=sa;r=0
        else:q=(abs(sa)//abs(sb))*(-1 if (sa<0)!=(sb<0) else 1);r=sa-q*sb
        value=q if funct3==4 else r
    else:
        q=0xffffffff if b==0 else a//b;r=a if b==0 else a%b
        value=q if funct3==5 else r
    return value&0xffffffff

def with_m(base_cpu):
    class RV32M(base_cpu):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);self.csr[0x301]=0x40001101;self.m_instructions=0
        def step(self):
            advance=self.bus.advance;advance()
            if self.csr[0x300]&8 and self.csr[0x304]&0x800 and self.bus.reg[0xc]&self.bus.reg[0x10]:
                self.csr[0x341]=self.pc;self.csr[0x342]=0x8000000b
                self.csr[0x300]=(self.csr[0x300]&~0x88)|0x80;self.pc=self.csr[0x305]&~3;self.bus.traps+=1
            instruction=self.read(self.pc,4)
            if instruction&127==0x33 and instruction>>25==1:
                rd=(instruction>>7)&31;a=self.r[(instruction>>15)&31];b=self.r[(instruction>>20)&31]
                result=multiply_divide(a,b,(instruction>>12)&7)
                if rd:self.r[rd]=result
                self.r[0]=0;self.pc=(self.pc+4)&0xffffffff;self.m_instructions+=1
            else:
                self.bus.advance=lambda:None
                try:super().step()
                finally:self.bus.advance=advance
    return RV32M
