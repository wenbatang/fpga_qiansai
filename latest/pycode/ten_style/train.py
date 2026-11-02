"""Distill selected frozen C8 INT8 teachers into ten independent full720 C6s."""
from pathlib import Path
import argparse,csv,hashlib,json,os,random,time
import numpy as np
from PIL import Image,ImageOps
import torch
from torch.nn import functional as F
from torchvision.transforms.functional import to_tensor
from catalog import ROOT,WS,CATALOG
from network import FullStyle as FloatStyle,rgb565,BASE
from hardware_qat import FullStyle as HardwareStyle
import teacher_integer

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def atomic(path,value):
    temp=path.with_suffix('.tmp');torch.save(value,temp);os.replace(temp,path)
def teachers(device='cuda'):
    output=[];fingerprints={}
    for item in CATALOG:
        folder=WS/'style_model/parameters/c8'/f'{item["source_id"]:02d}_{item["name"]}'
        params=folder/'parameters.npz';meta_path=folder/'metadata.json'
        d=np.load(params);meta=json.loads(meta_path.read_text(encoding='utf8'))
        assert meta['slot']==item['source_id'] and meta['name']==item['name']
        layers=[dict(info,w=d[f'w{i}'],b=d[f'b{i}'],shift=d[f'shift{i}']) for i,info in enumerate(meta['layers'])]
        output.append(teacher_integer.prepare_gpu(layers,device))
        for p in folder.glob('*'):
            if p.is_file():fingerprints[str(p)]=sha(p)
    return output,fingerprints
def augment(cache,size,batch):
    x=cache[torch.randint(len(cache),(batch,),device=cache.device)]
    room=x.shape[-1]-size;y=random.randrange(room+1);z=random.randrange(room+1)
    x=x[:,:,y:y+size,z:z+size]
    if random.random()<.5:x=x.flip(-1)
    if random.random()<.5:
        gain=torch.empty(batch,1,1,1,device=x.device).uniform_(.60,1.30)
        x=(x*gain).clamp(0,1).pow(random.uniform(.85,1.18))
    if random.random()<.25:
        gain=x.new_tensor([random.uniform(.9,1.1),random.uniform(1.,1.25),random.uniform(.9,1.1)])[None,:,None,None]
        x=(x*gain).clamp(0,1)
    return rgb565(x)
def loss_fn(y,target):
    fine=F.l1_loss(y,target)
    coarse=F.l1_loss(F.avg_pool2d(y,4),F.avg_pool2d(target,4))
    gradient=F.l1_loss(y[:,:,1:]-y[:,:,:-1],target[:,:,1:]-target[:,:,:-1])+F.l1_loss(y[:,:,:,1:]-y[:,:,:,:-1],target[:,:,:,1:]-target[:,:,:,:-1])
    # Reference means/contrast keep the distinct palettes during compression.
    moments=F.l1_loss(y.mean((-1,-2)),target.mean((-1,-2)))+F.l1_loss(y.std((-1,-2)),target.std((-1,-2)))
    return 5*fine+3*coarse+.7*gradient+.6*moments,fine,coarse,gradient
def main():
    p=argparse.ArgumentParser();p.add_argument('--run',default='ten_c6_v1');p.add_argument('--float-steps',type=int,default=8000);p.add_argument('--qat-steps',type=int,default=3000);p.add_argument('--size',type=int,default=128);p.add_argument('--batch',type=int,default=12);a=p.parse_args()
    assert torch.cuda.is_available() and a.float_steps%10==0 and a.qat_steps%10==0
    torch.set_num_threads(4);torch.backends.cudnn.benchmark=True
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    random.seed(20261102);np.random.seed(20261102);torch.manual_seed(20261102)
    run=ROOT/'runs'/a.run;run.mkdir(parents=True,exist_ok=True)
    assert not (run/'launch.json').exists(),'Existing training preserved'
    split_path=WS/'pycode/full720_style/runs/c6_v1/split.json';split=json.loads(split_path.read_text(encoding='utf8'))
    excluded=set(split['user_images_sha256'].values());assert split['all_user_images_excluded']
    assert not any(sha(path) in excluded for path in split['training'])
    assert set(split['training']).isdisjoint(split['validation'])
    (run/'split.json').write_text(json.dumps(split,ensure_ascii=False,indent=2),encoding='utf8')
    cached=[]
    for filename in split['training']:
        with Image.open(filename) as image:cached.append(to_tensor(ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'),(160,160),Image.Resampling.LANCZOS)))
    cache=torch.stack(cached).cuda();teacher_layers,teacher_hashes=teachers()
    warm=WS/'pycode/full720_style/runs/c6_v1/model.pt'
    warm_meta=torch.load(warm,map_location='cpu',weights_only=True)
    model=FloatStyle().cuda();warm_slots={0:0,3:1,4:2,34:3}
    for record,branch in zip(CATALOG,model.branches):
        slot=warm_slots.get(record['source_id'],0)
        values={k:(v[slot:slot+1] if '.affine.weight' in k else v) for k,v in warm_meta['model'].items()}
        branch.load_state_dict(values)
    model.freeze_bn();model.qat=False
    sources=[Path(__file__),ROOT/'network.py',ROOT/'hardware_qat.py',ROOT/'integer.py',ROOT/'teacher_integer.py',ROOT/'catalog.py',BASE,warm,split_path]
    hashes={str(path):sha(path) for path in sources}
    launch=dict(catalog=CATALOG,float_steps=a.float_steps,qat_steps=a.qat_steps,batch=a.batch,size=a.size,training_images=len(cache),teacher='actual frozen style_model/parameters/c8 int8 output',teacher_pool=True,student_pool=False,source_hashes=hashes,teacher_hashes=teacher_hashes,hardware_touched=False)
    (run/'launch.json').write_text(json.dumps(launch,ensure_ascii=False,indent=2),encoding='utf8')
    opt=torch.optim.Adam(model.parameters(),lr=.001)
    started=time.monotonic();total=a.float_steps+a.qat_steps
    with (run/'training.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['step','slot','source_id','loss','l1','coarse','gradient','seconds','hardware_qat'])
        for step in range(total):
            hardware=step>=a.float_steps
            if step==a.float_steps:
                revised=HardwareStyle().cuda();revised.load_state_dict(model.state_dict());model=revised;model.qat=True;model.freeze_bn();model.project()
                opt=torch.optim.Adam(model.parameters(),lr=.000045)
            slot=step%10;model.train();x=augment(cache,a.size,a.batch)
            with torch.no_grad():desired=teacher_integer.integer_torch(torch.floor(x*255+.5),teacher_layers[slot])/255
            opt.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16,enabled=not hardware):
                y=model(x,slot);loss,fine,coarse,gradient=loss_fn(y,desired)
            assert torch.isfinite(loss)
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),4);opt.step()
            if hardware:model.project(style=slot)
            else:
                for group in opt.param_groups:group['lr']=.00012+.00088*(1-step/a.float_steps)
            elapsed=time.monotonic()-started
            writer.writerow([step+1,slot,CATALOG[slot]['source_id'],float(loss.detach()),float(fine.detach()),float(coarse.detach()),float(gradient.detach()),elapsed,hardware])
            if (step+1)%250==0 or step+1==total:
                data=dict(family='ten_independent_full_c6',config=model.config,model={k:v.detach().cpu() for k,v in model.state_dict().items()},step=step+1,hardware_qat=hardware,qat=hardware,elapsed_seconds=elapsed,catalog=CATALOG,source_hashes=hashes,teacher_hashes=teacher_hashes,full_resolution=True,independent_styles=True,teacher_pool=True,student_pool=False,training_images=len(cache),float_steps=a.float_steps,qat_steps=a.qat_steps)
                atomic(run/'latest.pt',data)
                if not hardware:atomic(run/'float.pt',data)
                if step+1==total:atomic(run/'model.pt',data)
                status=dict(step=step+1,total=total,loss=float(loss.detach()),l1=float(fine.detach()),seconds=elapsed,hardware_qat=hardware)
                (run/'status.json').write_text(json.dumps(status,indent=2),encoding='utf8');stream.flush()
                print('TEN STYLE',status,flush=True)
    (run/'complete.json').write_text(json.dumps(dict(result='PASS',step=total,elapsed_seconds=elapsed,catalog=CATALOG,source_hashes=hashes,teacher_hashes=teacher_hashes),ensure_ascii=False,indent=2),encoding='utf8')
if __name__=='__main__':main()
