"""Actual full-resolution RTL vs independent int64 reference, including stalls."""
from pathlib import Path
import argparse,sys,re
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simutil import *
sys.path.insert(0,str(WS/'pycode/ten_style'))
from integer import integer_numpy


def main():
    p=argparse.ArgumentParser();p.add_argument('--width',type=int,default=24);p.add_argument('--height',type=int,default=40);p.add_argument('--styles',type=int,nargs='+',default=list(range(10)));a=p.parse_args()
    w,h=a.width,a.height;folder=ROOT/'sim'/f'ten_kernel_{w}x{h}';folder.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(83);data=rng.integers(0,256,(h,w,3),dtype=np.uint8)
    def write_image(path,image):path.write_text(''.join(f'{int(p[0])|(int(p[1])<<8)|(int(p[2])<<16):06x}\n' for p in image.reshape(-1,3)),encoding='ascii')
    write_image(folder/'input.mem',data);expected=np.stack([integer_numpy(data,layers(slot)) for slot in a.styles])
    write_image(folder/'expected.mem',expected);config_file(folder/'config.mem',a.styles)
    tb='''`timescale 1ns/1ps
module tb;
localparam W=WW,H=HH,N=W*H,S=SS;
reg clk=0;always #3 clk=~clk;reg reset=1,start=0;reg[23:0]din=0;reg iv=0,orr=0;wire ir,ov,done;wire[23:0]dout;
reg cv=0;reg[15:0]ca;reg[31:0]cd;reg[23:0]pixels[0:N-1],expected[0:S*N-1];reg[47:0]cfg[0:S*216-1];
integer i,s,ni=0,no=0,cycles=0,active=0,lasttake=0;reg[31:0]lfsr=32'had6527;
reg held=0;reg[23:0]held_data;
full_kernel #(.WIDTH(W),.HEIGHT(H),.FRAME_WIDTH(W)) dut(.clk(clk),.reset(reset),.start(start),.origin_x(16'sd0),.in_rgb(din),.in_valid(iv),.in_ready(ir),.out_rgb(dout),.out_valid(ov),.out_ready(orr),.done(done),.cfg_valid(cv),.cfg_address(ca),.cfg_data(cd),.split_mode(1'b0));
always @(posedge clk)if(active)begin
 cycles=cycles+1;lasttake=iv && ir;if(lasttake)ni=ni+1;
 if(held && (!ov || dout!==held_data))$fatal(1,"unstable held output");
 held=ov && !orr;held_data=dout;
 if(ov && orr)begin
  if(no>=N || dout!==expected[s*N+no])$fatal(1,"style%0d pixel%0d got%h expected%h ni%0d",s,no,dout,expected[s*N+no],ni);
  no=no+1;
 end
 if(cycles>10000000)$fatal(1,"timeout ni%0d no%0d DW%0d/%0d/%0d/%0d",ni,no,dut.block[0].spatial.state,dut.block[1].spatial.state,dut.block[2].spatial.state,dut.block[3].spatial.state);
end
always @(negedge clk)if(active)begin
 lfsr={lfsr[30:0],lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
 if(lasttake || !iv)begin iv=ni<N && lfsr[1:0]!=0;din=pixels[ni<N?ni:N-1];end
 orr=lfsr[4:2]!=0 && cycles%517>50;
end
initial begin
 $readmemh("input.mem",pixels);$readmemh("expected.mem",expected);$readmemh("config.mem",cfg);
 for(s=0;s<S;s=s+1)begin
  active=0;iv=0;orr=0;reset=1;repeat(5)@(negedge clk);reset=0;
  for(i=0;i<216;i=i+1)begin cv=1;{ca,cd}=cfg[s*216+i];@(negedge clk);end
  cv=0;ni=0;no=0;cycles=0;lasttake=0;held=0;start=1;@(negedge clk);start=0;active=1;
  wait(done);@(negedge clk);active=0;
  if(ni!=N || no!=N)$fatal(1,"pixel counts %0d %0d",ni,no);
  $display("PASS FULLRES kernel style%0d pixels%0d cycles%0d",s,no,cycles);
 end
 $finish;
end
endmodule
'''.replace('WW',str(w)).replace('HH',str(h)).replace('S=SS','S='+str(len(a.styles)))
    (folder/'tb.sv').write_text(tb,encoding='utf-8');files=[folder/'tb.sv',*core_sources()]
    text=questa(folder,files)
    receipt(folder,[*files,Path(__file__).resolve(),folder/'input.mem',folder/'expected.mem',folder/'config.mem'],
        'Full-resolution C6 learned RTL vs independent int64, random input gaps, long output stalls, boundaries and ten independent models; no FPGA or full SoC',
        styles=a.styles,width=w,height=h,pixels_per_style=w*h,integer_max_abs_error=0)
    print('\n'.join(line for line in text.splitlines() if 'PASS FULLRES' in line))


if __name__=='__main__':main()
