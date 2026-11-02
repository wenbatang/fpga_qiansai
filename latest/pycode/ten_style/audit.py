"""Read-only numerical/provenance audit of training and ten local exports."""
from pathlib import Path
import hashlib,json
import numpy as np
import torch
from catalog import ROOT,WS,CATALOG
from hardware_qat import load
from integer import model_layers
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    run=ROOT/'runs/ten_c6_v2';project=WS/'elinx/projects/camera_art_ten'
    model,data=load(run/'model.pt');launch=json.loads((run/'launch.json').read_text(encoding='utf8'))
    assert data['step']==11000 and data['hardware_qat'] and data['config']==dict(channels=6,styles=10)
    for p,h in {**data['source_hashes'],**data['teacher_hashes']}.items():assert sha(p)==h,p
    split=json.loads((run/'split.json').read_text(encoding='utf8'));excluded=set(split['user_images_sha256'].values())
    training={p:sha(p) for p in split['training']};validation={p:sha(p) for p in split['validation']}
    assert len(training)==512 and len(validation)==24 and set(training).isdisjoint(validation)
    assert set(training.values()).isdisjoint(excluded) and set(validation.values()).isdisjoint(excluded)
    assert len(excluded)==34
    records=[];rom=bytearray();bound=0
    for item in CATALOG:
        source=WS/'style_model/parameters/c8'/f'{item["source_id"]:02d}_{item["name"]}'
        sm=json.loads((source/'metadata.json').read_text(encoding='utf8'))
        assert sha(source/'parameters.npz')==sm['npz_sha256'] and sha(source/'parameters.bin')==sm['bin_sha256']
        folder=project/'parameters/c6'/f'{item["slot"]:02d}_{item["name"]}'
        meta=json.loads((folder/'metadata.json').read_text(encoding='utf8'));arrays=np.load(folder/'parameters.npz')
        for key in ['slot','source_id','name','label','gesture']:assert meta[key]==item[key]
        raw=bytearray();writes=0
        for i,layer in enumerate(model_layers(model,item['slot'])):
            for key in ['w','b','shift']:assert np.array_equal(arrays[f'{key}{i}'],layer[key])
            w=layer['w'].astype('i1').tobytes();b=layer['b'].astype('<i4').tobytes();s=layer['shift'].astype('u1').tobytes()
            wp=(-len(w))%4;sp=(-len(s))%4;raw.extend(w+bytes(wp)+b+s+bytes(sp));writes+=(len(w)+wp)//4+2*len(s)
            assert layer['clipped_weights']==0;bound=max(bound,layer['bound'])
        assert bytes(raw)==(folder/'parameters.bin').read_bytes() and len(raw)==712 and writes==216
        rom.extend(raw+bytes(736-len(raw)));records.append(dict(**item,parameter_sha256=sha(folder/'parameters.bin')))
    words=(project/'build/720p/weights.mem').read_text().split()
    actual=b''.join(int(word,16).to_bytes(4,'little') for word in words)
    assert bytes(rom)==actual and len(actual)==7360 and len(words)==1840 and bound<2**21
    result=dict(result='PASS',catalog=records,model_sha256=sha(run/'model.pt'),launch_sha256=sha(run/'launch.json'),training_step=11000,float_steps=8000,hardware_qat_steps=3000,training_images=512,validation_images=24,excluded_user_photos=34,training_hashes=training,validation_hashes=validation,user_photos_excluded=True,rom_bytes=7360,config_writes_per_style=216,weights_per_style=396,trainable_parameters=sum(p.numel() for p in model.parameters()),max_abs_sum_bound=bound,signed_accumulator_bits=22,source_hashes={str(path):sha(path) for path in [Path(__file__),run/'model.pt',run/'launch.json',run/'split.json',project/'build/720p/weights.mem',project/'build/model_selection.json',project/'build/accumulator_bound.json']})
    folder=ROOT/'results/final';folder.mkdir(parents=True,exist_ok=True)
    (folder/'checkpoint_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('PASS ten learned models/7360B ROM/216writes/22bit bound/data and teacher provenance; no board claim')
if __name__=='__main__':main()
