from pathlib import Path
import argparse,sys,re
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simutil import *
sys.path.insert(0,str(WS/'pycode/ten_style'))
from integer import integer_numpy


def main():
    p=argparse.ArgumentParser();p.add_argument('--full',action='store_true');p.add_argument('--styles',type=int,nargs='+');p.add_argument('--pressure',action='store_true');p.add_argument('--split',action='store_true');a=p.parse_args()
    assert not (a.full and a.pressure)
    w,h,core=(1280,720,320) if a.full else (128,24,48) if a.split else (128,24,48);slots=a.styles or ([9] if a.full else list(range(10)))
    folder=ROOT/'sim'/('ten_'+('full_split' if a.full and a.split else 'split_pressure' if a.split and a.pressure else 'split' if a.split else 'full' if a.full else 'dma_pressure' if a.pressure else 'dma'));folder.mkdir(parents=True,exist_ok=True)
    y,x=np.indices((h,w));r=((x*37+y*53)^(x>>3))&31;g=((x*11+y*7)^(y>>2))&63;b=(x*3+y*13)&31
    raw=((r<<11)|(g<<5)|b).astype(np.uint16);rgb=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),-1).astype(np.uint8)
    (folder/'raw.mem').write_text(''.join(f'{int(v):04x}\n' for v in raw.flat),encoding='ascii');expected=[]
    for slot in slots:
        pixels=integer_numpy(rgb,layers(slot));expected.append(((pixels[:,:,0].astype(np.uint16)>>3)<<11)|((pixels[:,:,1].astype(np.uint16)>>2)<<5)|(pixels[:,:,2]>>3))
        if a.split:expected[-1][:,:w//2]=raw[:,:w//2]
    (folder/'expected.mem').write_text(''.join(f'{int(v):04x}\n' for image in expected for v in image.flat),encoding='ascii');config_file(folder/'config.mem',slots)
    tb=(ROOT/'sim/templates/ten_dma_tb.sv').read_text(encoding='utf-8')
    tb=tb.replace('reg[1:0]style','reg[5:0]style').replace('.WIDTH(128),.HEIGHT(24),.TILE_CORE(48)',f'.WIDTH({w}),.HEIGHT({h}),.TILE_CORE({core}),.HALO(16)')
    tb=tb.replace('reg raw_mode=0;',"reg[1:0]output_bank=2;integer selected_bank=2;reg[29:0]expected_base=30'h00a00000;reg raw_mode=0;")
    tb=tb.replace(",1'b0,source_base",',output_bank,source_base')
    tb=tb.replace('awaddr>=3072*2',"awaddr<expected_base || awaddr>=expected_base+3072*2").replace('write_index<=awaddr/2','write_index<=(awaddr-expected_base)/2')
    tb=tb.replace("source_base=30'h00600000;start=1;","source_base=30'h00600000;output_bank=selected_bank;expected_base=selected_bank==2?30'h00a00000:selected_bank==1?30'h00200000:0;start=1;")
    tb=tb.replace("start=0;source_base=30'h00800000;","start=0;output_bank=3;source_base=30'h00800000;")
    if not a.full:tb=tb.replace('raw_mode=0;style=s;','selected_bank=s%3;raw_mode=0;style=s;')
    if a.split:
        tb=tb.replace('style=s;','style=32+s;').replace('inject=0;style=2;','inject=0;style=34;')
        # A mid-job UI change cannot alter the latched split flag or style.
        tb=tb.replace('raw_mode=!raw_mode;','raw_mode=!raw_mode;style=style^32;')
    if a.pressure:
        tb=tb.replace('t%7!=0','t%97>=55').replace('t%3!=0','t%89>=41').replace('bdelay<=17','bdelay<=97')
        for kind in [1,2]:tb=tb.replace(f'inject=={kind} && !injected && beat==3',f'inject=={kind} && !injected && write_count>=2 && beat==3')
        tb=tb.replace('(inject==3 && !injected)','(inject==3 && !injected && write_count>=2)').replace('if(inject==3 && !injected)injected<=1','if(inject==3 && !injected && write_count>=2)injected<=1')
    tb=tb.replace('3072',str(w*h)).replace('3071',str(w*h-1)).replace('12287',str(w*h*len(slots)-1)).replace('0:4867',f'0:{len(slots)*216-1}').replace('1217','216')
    old=ROOT.parent/'camera_art_styles'
    for name in ['config','raw','expected']:tb=tb.replace((old/f'sim/runtime/{name}.mem').as_posix(),(folder/f'{name}.mem').as_posix())
    tb=tb.replace('s<4',f's<{len(slots)}')
    ids='function integer style_id(input integer idx);begin case(idx)'+''.join(f'{i}:style_id={slot};' for i,slot in enumerate(slots))+'default:style_id=0;endcase end endfunction\n'
    tb=tb.replace('module tiles_tb;','module tiles_tb;\n'+ids).replace('style=s;','style=style_id(s);').replace('style=32+s;','style=32+style_id(s);')
    if a.full:
        tb=tb.replace('8000000','200000000')
        start=tb.index(' for(s=1;s<=3;');tb=tb[:start]+' $display("PASS FULL C6 frame");$finish;end endmodule\n'
    (folder/'tb.sv').write_text(tb,encoding='utf-8')
    files=[folder/'tb.sv',*[ROOT/'rtl/p720'/n for n in ['video_tile_engine_async.sv','video_cnn_async.sv','stream_fifo_24.sv']],ROOT/'rtl/reset_sync.sv',*core_sources(),ROOT/'vendor/rtl/ddr3_controller/common/efx_fifo_v2.3/efx_fifo_wrapper.v']
    log=questa(folder,files,'tiles_tb')
    cases=[dict(slot=slots[int(i)],pixels=w*h,ui_cycles=int(c),model_fps=100000000/int(c),integer_max_abs_error=0) for i,c in re.findall(r'PASS style (\d+) exact integer pixels, cycles=(\d+)',log)]
    assert len(cases)==len(slots)
    receipt(folder,[*files,Path(__file__).resolve(),folder/'raw.mem',folder/'expected.mem',folder/'config.mem',WS/'pycode/ten_style/integer.py',ROOT/'sim/templates/ten_dma_tb.sv'],
        'Full-resolution C6 CNN/DMA, real asynchronous FIFO, bounded AXI, learned integer outputs/seams/edges/finalB; no physical DDR/camera/HDMI concurrency',
        pixels=w*h,styles=slots,split=a.split,ui_hz=100000000,cnn_period_ns=6.002,tile_core=core,halo=16,per_style=cases,
        min_model_fps=min(c['model_fps'] for c in cases),ui_cycles=cases[-1]['ui_cycles'],model_fps=cases[-1]['model_fps'])
    print('\n'.join(line for line in log.splitlines() if 'PASS' in line))


if __name__=='__main__':main()
