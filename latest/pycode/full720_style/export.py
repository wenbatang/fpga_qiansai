"""Freeze local C6 full720 exports and exact aligned RISC-V ROM layout."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import torch
from network import load
from integer import model_layers
ROOT=Path(__file__).resolve().parent;WS=ROOT.parents[1]
NAMES=['vangogh','papercut','comic','inkwash']


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def packed(values,bits):
    v=np.asarray(values).flatten();n=sum((int(x)&((1<<bits)-1))<<(i*bits) for i,x in enumerate(v));return f"{len(v)*bits}'h{n:x}"


def write_exports(all_layers,project,source):
    assert not (project/'build/720p/build_inputs.json').exists(),'Mapped model must remain frozen'
    project.mkdir(parents=True,exist_ok=True);blob=bytearray();selection=[];maximum=0
    for slot,(name,layers) in enumerate(zip(NAMES,all_layers)):
        folder=project/'parameters/c6'/f'{slot:02d}_{name}';folder.mkdir(parents=True,exist_ok=True)
        np.savez(folder/'parameters.npz',**{f'{key}{i}':l[key] for i,l in enumerate(layers) for key in ['w','b','shift']})
        raw=bytearray();meta=[];writes=0
        for i,l in enumerate(layers):
            w=l['w'].astype('i1').tobytes();bias=l['b'].astype('<i4').tobytes();sh=l['shift'].astype('u1').tobytes()
            wp=(-len(w))%4;sp=(-len(sh))%4;raw.extend(w+bytes(wp)+bias+sh+bytes(sp));writes+=(len(w)+wp)//4+2*len(sh)
            for key,bits in [('w',8),('b',32),('shift',8)]:
                (folder/f'layer{i}_{key}.mem').write_text(''.join(f'{int(v)&((1<<bits)-1):0{bits//4}x}\n' for v in l[key].flatten()),encoding='ascii')
            bound=int((np.abs(l['w'].astype(np.int64)).sum((1,2,3))*255+np.abs(l['b'].astype(np.int64))).max());maximum=max(maximum,bound)
            meta.append(dict(d=l['d'],groups=l['groups'],signed=l['signed'],shape=list(l['w'].shape),weight_bytes=len(w),weight_padded=len(w)+wp,channels=len(sh),shift_padded=len(sh)+sp,bound=bound))
        assert len(raw)==712 and writes==216
        (folder/'parameters.bin').write_bytes(raw);blob.extend(raw+bytes(736-len(raw)))
        record=dict(slot=slot,name=name,architecture='full_c6',full_resolution=True,weights=396,bytes=len(raw),stride_bytes=736,config_writes=216,layers=meta,npz_sha256=sha(folder/'parameters.npz'),bin_sha256=sha(folder/'parameters.bin'))
        (folder/'metadata.json').write_text(json.dumps(record,indent=2),encoding='utf-8');selection.append(record)
    text='// Frozen shared DW/head from trained full-resolution C6 exports.\nmodule full_shared_params #(parameter LAYER=1,NW=54,COUT=6)(output wire[NW*8-1:0]weights,output wire[COUT*24-1:0]biases,output wire[COUT*5-1:0]shifts);\ngenerate\n'
    for index,layer in enumerate([1,3,5,7,9]):
        base=all_layers[0][layer]
        for layers in all_layers:
            for key in ['w','b','shift']:assert np.array_equal(layers[layer][key],base[key]),'Shared layers must be identical'
        text+=('if' if index==0 else 'else if')+f'(LAYER=={layer})begin\nassign weights={packed(base["w"],8)};assign biases={packed(base["b"],24)};assign shifts={packed(base["shift"],5)};end\n'
    text+='else begin assign weights=0;assign biases=0;assign shifts=0;end\nendgenerate\nendmodule\n'
    (project/'rtl/full_shared_params.sv').write_text(text,encoding='ascii')
    b=project/'build/720p';b.mkdir(parents=True,exist_ok=True)
    (b/'weights.mem').write_text(''.join(f'{int.from_bytes(blob[i:i+4],"little"):08x}\n' for i in range(0,len(blob),4)),encoding='ascii')
    assert len(blob)==2944 and maximum<2**23
    (project/'build/model_selection.json').write_text(json.dumps(dict(styles=selection,rom_bytes=len(blob),stride_bytes=736,source=str(source),source_sha256=sha(source),trained_this_turn=True,downsample=False,receptive_field=31),indent=2),encoding='utf-8')
    (project/'build/accumulator_bound.json').write_text(json.dumps(dict(result='PASS',max_abs_sum_bound=maximum,styles_compared=4,signed_accumulator_bits=24),indent=2),encoding='utf-8')
    print('EXPORTED full_c6 4styles 396weights/style ROM2944B cfg216 bound',maximum)


def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,default=ROOT/'runs/c6_v1/model.pt');p.add_argument('--project',type=Path,default=WS/'elinx/projects/camera_full720_30');a=p.parse_args()
    model,data=load(a.checkpoint);write_exports([model_layers(model,i) for i in range(4)],a.project,a.checkpoint)


if __name__=='__main__':main()
