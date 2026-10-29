from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1];STYLE=ROOT;OLD=ROOT.parent/'camera_art_styles'
sys.path.insert(0,str(Path(__file__).parent));from desktop_process import run
Q=Path('E:/softare_FPGA/questasim/root/win64');IV=Path('E:/softare_FPGA/iverilog/iverilog/bin')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def configs(slot):
    import numpy as np
    folder=next((STYLE/'parameters/c8').glob(f'{slot:02d}_*'));d=np.load(folder/'parameters.npz');words=[]
    for layer in range(10):
        w=d[f'w{layer}'].flatten()
        for i in range(0,len(w),4):words.append(((layer<<12)|i,sum((int(v)&255)<<(8*j) for j,v in enumerate(w[i:i+4]))))
        for c,b in enumerate(d[f'b{layer}']):words.append(((layer<<12)|0x400|c,int(b)&0xffffffff))
        for c,s in enumerate(d[f'shift{layer}']):words.append(((layer<<12)|0x800|c,int(s)))
    assert len(words)==346
    return words
def config_file(path,slots):path.write_text(''.join(f'{a:04x}{d:08x}\n' for slot in slots for a,d in configs(slot)),encoding='ascii')
def questa(folder,files,top):
    for n,args in [('vlib',['work']),('vlog',['-sv','-timescale','1ns/1ps',*map(str,files)]),('vsim',['-c','-t','ps',top,'-do','run -all; quit -f'])]:assert run([str(Q/(n+'.exe')),*args],folder,folder/(n+'.log'))==0,n
    text=(folder/'vsim.log').read_text(encoding='utf-8',errors='replace');assert 'PASS' in text and '** Fatal:' not in text,text[-2000:];return text
def receipt(folder,files,scope,extra=None):
    r=dict(result='PASS',scope=scope,sources_sha256={str(p):sha(p) for p in files},logs_sha256={str(folder/'vsim.log'):sha(folder/'vsim.log')})
    if extra:r.update(extra)
    (folder/'verification.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
