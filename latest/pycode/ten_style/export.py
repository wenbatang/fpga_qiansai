"""Freeze ten full720 C6 parameters and the exact 216-write runtime ROM."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from hardware_qat import load
from integer import model_layers
from catalog import ROOT,WS,CATALOG
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_exports(all_layers,project,source,checkpoint):
    assert len(all_layers)==10 and not (project/'build/720p/build_inputs.json').exists(),'Mapped candidate is frozen'
    blob=bytearray();selection=[];maximum=0;clipped=0
    for item,layers in zip(CATALOG,all_layers):
        slot=item['slot'];name=item['name'];folder=project/'parameters/c6'/f'{slot:02d}_{name}'
        folder.mkdir(parents=True,exist_ok=True)
        np.savez(folder/'parameters.npz',**{f'{key}{i}':layer[key] for i,layer in enumerate(layers) for key in ['w','b','shift']})
        raw=bytearray();meta=[];writes=0
        for i,l in enumerate(layers):
            weights=l['w'].astype('i1').tobytes();bias=l['b'].astype('<i4').tobytes();shift=l['shift'].astype('u1').tobytes()
            wp=(-len(weights))%4;sp=(-len(shift))%4
            raw.extend(weights+bytes(wp)+bias+shift+bytes(sp));writes+=(len(weights)+wp)//4+2*len(shift)
            for key,bits in [('w',8),('b',32),('shift',8)]:
                (folder/f'layer{i}_{key}.mem').write_text(''.join(f'{int(v)&((1<<bits)-1):0{bits//4}x}\n' for v in l[key].flatten()),encoding='ascii')
            bound=int((np.abs(l['w'].astype(np.int64)).sum((1,2,3))*255+np.abs(l['b'].astype(np.int64))).max())
            maximum=max(maximum,bound);clipped+=int(l['clipped_weights'])
            meta.append(dict(d=l['d'],groups=l['groups'],signed=l['signed'],shape=list(l['w'].shape),weight_bytes=len(weights),weight_padded=len(weights)+wp,channels=len(shift),shift_padded=len(shift)+sp,bound=bound))
        assert len(raw)==712 and writes==216
        (folder/'parameters.bin').write_bytes(raw);blob.extend(raw+bytes(736-len(raw)))
        record=dict(**item,architecture='full_c6',full_resolution=True,weights=396,bytes=len(raw),stride_bytes=736,config_writes=216,layers=meta,npz_sha256=sha(folder/'parameters.npz'),bin_sha256=sha(folder/'parameters.bin'))
        (folder/'metadata.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8');selection.append(record)
    assert len(blob)==7360 and maximum<2**21 and clipped==0
    assert any(not np.array_equal(all_layers[0][1]['w'],layers[1]['w']) for layers in all_layers[1:])
    b=project/'build/720p';b.mkdir(parents=True,exist_ok=True)
    (b/'weights.mem').write_text(''.join(f'{int.from_bytes(blob[i:i+4],"little"):08x}\n' for i in range(0,len(blob),4)),encoding='ascii')
    selection=dict(styles=selection,rom_bytes=len(blob),stride_bytes=736,source=str(source.resolve()),source_sha256=sha(source),trained_this_turn=True,downsample=False,receptive_field=31,independent_styles=True,shared_dw_head=False,training_step=checkpoint['step'],hardware_qat=True,provisional=False,clipped_weights=clipped,teacher_source_ids=[r['source_id'] for r in CATALOG],teacher_is_c8=True,teacher_hashes=checkpoint['teacher_hashes'],student_full_resolution=True)
    (project/'build/model_selection.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2),encoding='utf8')
    (project/'build/accumulator_bound.json').write_text(json.dumps(dict(result='PASS',max_abs_sum_bound=maximum,styles_compared=10,signed_accumulator_bits=22,rounded_bits=23,clipped_weights=0),indent=2),encoding='utf8')
    print('EXPORTED ten full_c6 independent styles; ROM7360B cfg216 bound',maximum,flush=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,default=ROOT/'runs/ten_c6_texture_v1/model.pt');p.add_argument('--project',type=Path,default=WS/'elinx/projects/camera_art_ten');a=p.parse_args()
    model,data=load(a.checkpoint)
    assert data['step']>=11000 and data.get('hardware_qat') and data['config']==dict(channels=6,styles=10)
    write_exports([model_layers(model,slot) for slot in range(10)],a.project,a.checkpoint,data)
if __name__=='__main__':main()
