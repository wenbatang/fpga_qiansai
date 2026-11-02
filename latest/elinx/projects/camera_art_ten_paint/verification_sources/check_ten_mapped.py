"""Independent integer check of Efinity primitive netlists, no receipt reuse."""
from pathlib import Path
import argparse,json,re,shutil,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simutil import *
sys.path.insert(0,str(WS/'pycode/ten_style'))
from integer import integer_numpy


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dma',action='store_true');a=parser.parse_args()
    folder=ROOT/'sim'/('ten_mapped_dma' if a.dma else 'ten_mapped');folder.mkdir(parents=True,exist_ok=True)
    build=ROOT/'build'/('probe_dma' if a.dma else 'probe');top='full_dma_probe' if a.dma else 'full_probe'
    binding=build/'inputs.json';inputs=json.loads(binding.read_text(encoding='utf-8'))
    for p,digest in inputs.items():assert sha(p)==digest,'OOC source changed'
    if a.dma:
        original=ROOT/'sim/ten_split';tb=(original/'tb.sv').read_text(encoding='utf-8')
        # Generate a local128x24 reference using the exact same public DMA TB.
        w,h,core=128,24,48;y,x=np.indices((h,w));r=((x*37+y*53)^(x>>3))&31;g=((x*11+y*7)^(y>>2))&63;b=(x*3+y*13)&31
        raw=((r<<11)|(g<<5)|b).astype(np.uint16);rgb=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),-1).astype(np.uint8)
        out=[]
        for slot in range(10):
            image=integer_numpy(rgb,layers(slot));out.append(((image[:,:,0].astype(np.uint16)>>3)<<11)|((image[:,:,1].astype(np.uint16)>>2)<<5)|(image[:,:,2]>>3))
            out[-1][:,:w//2]=raw[:,:w//2]
        (folder/'raw.mem').write_text(''.join(f'{int(v):04x}\n' for v in raw.flat),encoding='ascii')
        (folder/'expected.mem').write_text(''.join(f'{int(v):04x}\n' for image in out for v in image.flat),encoding='ascii');config_file(folder/'config.mem',range(10))
        tb,count=re.subn(r'video_tile_engine_async\s*#\(.*?\)\s+engine\(','full_dma_probe engine(',tb,count=1,flags=re.S);assert count==1
        tb=tb.replace('10239','3071').replace('10240','3072').replace('40959','12287').replace(original.as_posix(),folder.as_posix())
        tbtop='tiles_tb';pixels=w*h
    else:
        w,h=24,40;rng=np.random.default_rng(193);data=rng.integers(0,256,(h,w,3),dtype=np.uint8)
        def write(path,array):path.write_text(''.join(f'{int(v[0])|(int(v[1])<<8)|(int(v[2])<<16):06x}\n' for v in array.reshape(-1,3)),encoding='ascii')
        write(folder/'input.mem',data);write(folder/'expected.mem',np.stack([integer_numpy(data,layers(slot)) for slot in range(10)]));config_file(folder/'config.mem',range(10))
        tb=(ROOT/'sim/ten_kernel_24x40/tb.sv').read_text(encoding='utf-8').replace('W=48,H=40','W=24,H=40')
        tb,count=re.subn(r'full_kernel\s*#\(.*?\)\s+dut\(','full_probe dut(',tb,count=1,flags=re.S);assert count==1
        tb=tb.replace(".origin_x(16'sd0),",'')
        tb=tb.replace(",.split_mode(1'b0)",'')
        tb=tb.replace('dut.block[0].spatial.state,dut.block[1].spatial.state,dut.block[2].spatial.state,dut.block[3].spatial.state','0,0,0,0')
        tbtop='tb';pixels=w*h
    (folder/'tb.sv').write_text(tb,encoding='utf-8');net=build/'outflow'/(top+'.map.v')
    models=sorted(Path('E:/software/efinity/sim_models/verilog').glob('*.v'));files=[*models,net,folder/'tb.sv']
    output=questa(folder,files,tbtop)
    if a.dma:assert all(f'PASS style {slot} exact' in output for slot in range(10))
    else:assert output.count('PASS FULLRES kernel style')==10
    receipt(folder,[*files,*map(Path,inputs),binding,Path(__file__).resolve(),*[p for p in folder.glob('*.mem')]],
        'Actual Efinity2026.1.132 EFX primitives vs independent int64; full-resolution C6 ten models with stalls'+('; DMA/asyncFIFO/3banks/finalB/errors/recovery/raw' if a.dma else '; convolution bank conflicts and contexts'),
        styles=list(range(10)),split=a.dma,pixels_per_style=pixels,integer_max_abs_error=0)
    print('PASS mapped',top,'tenstyles',pixels,'pixels/style')


if __name__=='__main__':main()
