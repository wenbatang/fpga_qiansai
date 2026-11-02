"""Preserved second candidate: texture statistics without copying pool phase."""
from pathlib import Path
import argparse,csv,json,random,time,importlib.util
import torch
from torch import nn
from torch.nn import functional as F
from PIL import Image,ImageOps
from torchvision.transforms.functional import to_tensor
from torchvision.models.vgg import make_layers
from catalog import ROOT,WS,CATALOG
from hardware_qat import load
from train import sha,teachers,augment,atomic
import teacher_integer
VGG_PATH=Path(torch.hub.get_dir())/'checkpoints/vgg19-dcbb9e9d.pth'
class TextureVGG(nn.Module):
    def __init__(self):
        super().__init__();self.layers=make_layers([64,64,'M',128,128])
        d=torch.load(VGG_PATH,map_location='cpu',weights_only=True)
        self.layers.load_state_dict({k.removeprefix('features.'):v for k,v in d.items() if k.startswith('features.') and int(k.split('.')[1])<len(self.layers)})
        self.requires_grad_(False);self.register_buffer('mean',torch.tensor([.485,.456,.406])[None,:,None,None]);self.register_buffer('std',torch.tensor([.229,.224,.225])[None,:,None,None])
    def forward(self,x):
        x=(x-self.mean)/self.std;out=[]
        for i,l in enumerate(self.layers):
            x=l(x)
            if i in [3,8]:out.append(x)
        return out
def gram(x):
    n,c,h,w=x.shape;x=x.float().flatten(2);return x@x.transpose(1,2)/(c*h*w)
def energies(x):
    return [F.avg_pool2d((x[:,:,1:]-x[:,:,:-1]).abs(),4),F.avg_pool2d((x[:,:,:,1:]-x[:,:,:,:-1]).abs(),4)]
def main():
    p=argparse.ArgumentParser();p.add_argument('--steps',type=int,default=3000);p.add_argument('--batch',type=int,default=6);p.add_argument('--run',default='ten_c6_texture_v1');a=p.parse_args()
    assert a.steps%10==0
    torch.set_num_threads(4);torch.backends.cudnn.benchmark=True;torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False;torch.manual_seed(20261103);random.seed(20261103)
    source=ROOT/'runs/ten_c6_v2/model.pt';model,meta=load(source,'cuda');model.freeze_bn();model.qat=True
    run=ROOT/'runs'/a.run;run.mkdir(parents=True,exist_ok=True);assert not (run/'launch.json').exists()
    split_path=ROOT/'runs/ten_c6_v2/split.json';split=json.loads(split_path.read_text(encoding='utf8'))
    (run/'split.json').write_text(json.dumps(split,ensure_ascii=False,indent=2),encoding='utf8')
    cache=[]
    for filename in split['training']:
        with Image.open(filename) as image:cache.append(to_tensor(ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'),(160,160),Image.Resampling.LANCZOS)))
    cache=torch.stack(cache).cuda();teacher_layers,teacher_hashes=teachers();vgg=TextureVGG().cuda().eval()
    hashes={**meta['source_hashes'],**{str(path):sha(path) for path in [source,Path(__file__),VGG_PATH]}}
    (run/'launch.json').write_text(json.dumps(dict(source=str(source),source_sha256=sha(source),steps=a.steps,batch=a.batch,source_hashes=hashes,teacher_hashes=teacher_hashes,scope='Frozen shallow VGG/gradient texture statistics, source C8 INT8 targets; new candidate preserves base'),ensure_ascii=False,indent=2),encoding='utf8')
    opt=torch.optim.Adam(model.parameters(),lr=.00006);started=time.monotonic()
    with (run/'training.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['step','slot','loss','pixel_l1','texture','energy','seconds'])
        for step in range(a.steps):
            slot=step%10;model.train();x=augment(cache,128,a.batch)
            with torch.no_grad():
                target=teacher_integer.integer_torch((x*255).round(),teacher_layers[slot])/255
                with torch.autocast('cuda',dtype=torch.bfloat16):target_grams=[gram(z) for z in vgg(target)]
                target_energy=energies(target)
            opt.zero_grad(set_to_none=True);y=model(x,slot)
            with torch.autocast('cuda',dtype=torch.bfloat16):
                texture=sum(F.mse_loss(gram(z),g) for z,g in zip(vgg(y),target_grams))
            fine=F.l1_loss(y,target);coarse=F.l1_loss(F.avg_pool2d(y,8),F.avg_pool2d(target,8))
            energy=sum(F.l1_loss(z,g) for z,g in zip(energies(y),target_energy))
            loss=2*fine+2*coarse+200000*texture+2*energy
            assert torch.isfinite(loss);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),4);opt.step();model.project(style=slot)
            elapsed=time.monotonic()-started;writer.writerow([step+1,slot,float(loss.detach()),float(fine.detach()),float(texture.detach()),float(energy.detach()),elapsed])
            if (step+1)%250==0 or step+1==a.steps:
                data=dict(meta,step=meta['step']+step+1,texture_refinement_steps=step+1,source_hashes=hashes,model={k:v.detach().cpu() for k,v in model.state_dict().items()},elapsed_seconds=meta['elapsed_seconds']+elapsed,teacher_hashes=teacher_hashes)
                atomic(run/'latest.pt',data)
                if step+1==a.steps:atomic(run/'model.pt',data)
                (run/'status.json').write_text(json.dumps(dict(step=step+1,loss=float(loss.detach()),texture=float(texture.detach()),energy=float(energy.detach()),seconds=elapsed),indent=2),encoding='utf8');stream.flush()
                print('TEXTURE QAT',step+1,round(float(loss.detach()),4),'energy',round(float(energy.detach()),4),'seconds',round(elapsed,1),flush=True)
    (run/'complete.json').write_text(json.dumps(dict(result='PASS',steps=a.steps,model_step=data['step'],elapsed_seconds=elapsed,source_hashes=hashes),indent=2),encoding='utf8')
if __name__=='__main__':main()
