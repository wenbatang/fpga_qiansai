from pathlib import Path
import sys,json,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2];OLD=ROOT.parent/'camera_art_styles'
sys.path.insert(0,str(WS/'pycode/full720_style'));sys.path.insert(0,str(ROOT/'scripts'))
from desktop_process import run
Q=Path('E:/softare_FPGA/questasim/root/win64')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def layers(slot):
    folder=next((ROOT/'parameters/c6').glob(f'{slot:02d}_*'));d=np.load(folder/'parameters.npz');m=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
    return [dict(info,w=d[f'w{i}'],b=d[f'b{i}'],shift=d[f'shift{i}']) for i,info in enumerate(m['layers'])]
def configs(slot):
    words=[]
    for i,l in enumerate(layers(slot)):
        weights=list(l['w'].flatten());weights.extend([0]*((-len(weights))%4))
        for offset in range(0,len(weights),4):words.append(((i<<12)|offset,sum((int(v)&255)<<(8*j) for j,v in enumerate(weights[offset:offset+4]))))
        for c,v in enumerate(l['b']):words.append(((i<<12)|0x400|c,int(v)&0xffffffff))
        for c,v in enumerate(l['shift']):words.append(((i<<12)|0x800|c,int(v)))
    assert len(words)==216
    return words
def config_file(path,slots):path.write_text(''.join(f'{a:04x}{d:08x}\n' for s in slots for a,d in configs(s)),encoding='ascii')
def core_sources():return [ROOT/'rtl'/n for n in ['style_line_ram.sv','full_shared_params.sv','full_pointwise.sv','full_dw3x3.sv','full_kernel.sv','full_view.sv']]
def questa(folder,files,top='tb'):
    folder.mkdir(parents=True,exist_ok=True)
    for name,args in [('vlib',['work']),('vlog',['-sv','-timescale','1ns/1ps',*map(str,files)]),('vsim',['-c','-t','ps',top,'-do','run -all; quit -f'])]:
        assert run([str(Q/(name+'.exe')),*args],folder,folder/(name+'.log'))==0,(name,(folder/(name+'.log')).read_text(encoding='utf-8',errors='replace')[-2000:])
    text=(folder/'vsim.log').read_text(encoding='utf-8',errors='replace')
    assert 'PASS' in text and '** Fatal:' not in text,text[-2500:]
    return text
def receipt(folder,files,scope,extra=None,**details):
    files=list(dict.fromkeys([*files,Path(__file__).resolve()]))
    for slot in range(4):files.extend(next((ROOT/'parameters/c6').glob(f'{slot:02d}_*')).glob('*'))
    payload=dict(extra or {});payload.update(details)
    result=dict(result='PASS',scope=scope,sources_sha256={str(p):sha(p) for p in files if p.is_file()},logs_sha256={str(p):sha(p) for p in folder.glob('*.log')},**payload)
    assert result['sources_sha256'] and result['logs_sha256']
    (folder/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
