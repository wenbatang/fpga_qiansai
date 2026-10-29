"""Train four full-resolution styles, preserving all earlier models and datasets."""
from pathlib import Path
import argparse,hashlib,json,os,random,time,csv,importlib.util
import numpy as np
from PIL import Image,ImageOps
import torch
from torch import nn
from torch.nn import functional as F
from torchvision.models.vgg import make_layers
from torchvision.transforms.functional import to_tensor
from network import FullStyle,rgb565

ROOT=Path(__file__).resolve().parent;WS=ROOT.parents[1]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tensor(path,size):
    with Image.open(path) as image:return to_tensor(ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'),(size,size),Image.Resampling.LANCZOS))
def gram(x):
    b,c,h,w=x.shape;x=x.float().flatten(2);return x@x.transpose(1,2)/(c*h*w)


class VGG(nn.Module):
    def __init__(self):
        super().__init__();self.layers=make_layers([64,64,'M',128,128,'M',256,256,256,256,'M',512])
        p=Path('C:/Users/wenbatang/.cache/torch/hub/checkpoints/vgg19-dcbb9e9d.pth')
        s=torch.load(p,map_location='cpu',weights_only=True)
        self.layers.load_state_dict({k.removeprefix('features.'):v for k,v in s.items() if k.startswith('features.') and int(k.split('.')[1])<len(self.layers)})
        self.requires_grad_(False);self.register_buffer('mean',torch.tensor([.485,.456,.406])[None,:,None,None]);self.register_buffer('std',torch.tensor([.229,.224,.225])[None,:,None,None])
    def forward(self,x):
        x=(x-self.mean)/self.std;out=[]
        for i,l in enumerate(self.layers):
            x=l(x)
            if i in [3,8,17,20]:out.append(x)
        return out


class Teacher:
    def __init__(self):
        self.layers=[];self.hashes={}
        for source_slot in [0,3,4,5]:
            folder=next((WS/'style_model/parameters/c8').glob(f'{source_slot:02d}_*'))
            d=np.load(folder/'parameters.npz');metadata=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
            self.layers.append([dict(m,w=torch.tensor(d[f'w{i}'].astype(np.float32),device='cuda'),b=torch.tensor(d[f'b{i}'].astype(np.float32),device='cuda'),shift=torch.tensor(d[f'shift{i}'],device='cuda')) for i,m in enumerate(metadata['layers'])])
            self.hashes[str(folder/'parameters.npz')]=sha(folder/'parameters.npz')
    @torch.no_grad()
    def __call__(self,x,styles):
        out=torch.empty_like(x)
        for slot in range(4):
            index=(styles==slot).nonzero().flatten()
            if not len(index):continue
            z=x[index]*255;layers=self.layers[slot]
            def conv(v,l):
                if l['w'].shape[-1]>1:
                    d=l['d'];v=F.pad(v,(d,d,0,0),mode='reflect' if v.shape[-1]>d else 'replicate');v=F.pad(v,(0,0,d,d),mode='reflect' if v.shape[-2]>d else 'replicate')
                a=F.conv2d(v,l['w'],l['b'],dilation=l['d'],groups=l['groups']);s=l['shift'][None,:,None,None]
                q=torch.floor((a+torch.where(s>0,2.**(s-1),0))/(2.**s))
                return q.clamp(-510,510) if l['signed'] else q.clamp(0,255)
            h=conv(torch.floor(F.avg_pool2d(z,2)+.5),layers[0])
            for i in [1,3,5,7]:h=(h+conv(conv(h,layers[i]),layers[i+1])).clamp(0,255)
            out[index]=(z+conv(h,layers[9]).repeat_interleave(2,-2).repeat_interleave(2,-1)).clamp(0,255)/255
        return out


def save(path,model,opt,meta):
    data=dict(meta,config=model.config,qat=model.qat,model={k:v.detach().cpu() for k,v in model.state_dict().items()},optimizer=opt.state_dict())
    temp=path.with_suffix('.tmp');torch.save(data,temp);os.replace(temp,path)


def main():
    p=argparse.ArgumentParser();p.add_argument('--steps',type=int,default=6000);p.add_argument('--size',type=int,default=96);p.add_argument('--batch',type=int,default=12);p.add_argument('--channels',type=int,default=6);p.add_argument('--run',default='c6_v1');p.add_argument('--resume',action='store_true');a=p.parse_args()
    assert a.size%2==0 and a.batch%4==0 and torch.cuda.is_available()
    random.seed(20261030);np.random.seed(20261030);torch.manual_seed(20261030);torch.set_num_threads(4)
    torch.backends.cudnn.benchmark=True;torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
    run=ROOT/'runs'/a.run;run.mkdir(parents=True,exist_ok=True)
    if (run/'latest.pt').exists() and not a.resume:raise FileExistsError('Use --resume or another run')
    # Reuse the frozen reference split; no demonstration image enters training.
    split=json.loads((WS/'style_model/runs/tiny47_c8_final/split.json').read_text(encoding='utf-8'))
    training=[Path(x) for x in split['training']];validation=[Path(x) for x in split['validation']]
    (run/'split.json').write_text(json.dumps(split,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CACHE',len(training),'train',len(validation),'validation',flush=True)
    cache=torch.stack([tensor(path,a.size) for path in training]).cuda()
    teacher=Teacher();vgg=VGG().cuda().eval();model=FullStyle(a.channels).cuda();opt=torch.optim.Adam(model.parameters(),lr=.002)
    start=0;elapsed=0
    if a.resume:
        old=torch.load(run/'latest.pt',map_location='cpu',weights_only=True);model.load_state_dict(old['model']);opt.load_state_dict(old['optimizer']);start=old['step'];elapsed=old['elapsed_seconds'];model.qat=old['qat']
    t0=time.monotonic();source_hashes={str(path):sha(path) for path in ROOT.glob('*.py')}
    (run/'launch.json').write_text(json.dumps(dict(sources=source_hashes,teacher=teacher.hashes,steps=a.steps,batch=a.batch,size=a.size,architecture='full_resolution_c6_dw_pw',downsample=False),indent=2),encoding='utf-8')
    with (run/'training.csv').open('a',newline='') as f:
        writer=csv.writer(f)
        if not start:writer.writerow(['step','loss','distill','gradient','content','style','seconds','qat'])
        for step in range(start,a.steps):
            if step>=800:model.freeze_bn()
            model.qat=step>=int(a.steps*.76);model.train()
            styles=torch.arange(a.batch,device='cuda')%4;styles=styles[torch.randperm(a.batch,device='cuda')]
            x=cache[torch.randint(len(cache),(a.batch,),device='cuda')]
            if random.random()<.5:x=x.flip(-1)
            # Include moderate dimming; avoid forcing a dark camera into a single color.
            if random.random()<.25:x=x*(.35+.65*random.random())
            x=rgb565(x)
            target=teacher(x,styles)
            with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):tf=vgg(target);target_grams=[gram(z) for z in tf];content_target=vgg(x)[2].float()
            opt.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16):
                y=model(x,styles);features=vgg(y)
                distill=F.l1_loss(y,target)
                gradient=F.l1_loss(y[:,:,1:]-y[:,:,:-1],target[:,:,1:]-target[:,:,:-1])+F.l1_loss(y[:,:,:,1:]-y[:,:,:,:-1],target[:,:,:,1:]-target[:,:,:,:-1])
                content=F.mse_loss(features[2].float(),content_target)
                style=sum(F.mse_loss(gram(z),g) for z,g in zip(features,target_grams))
                palette=F.mse_loss(y.mean((2,3)),target.mean((2,3)))
                tv=(y[:,:,1:]-y[:,:,:-1]).abs().mean()+(y[:,:,:,1:]-y[:,:,:,:-1]).abs().mean()
                loss=18*distill+3*gradient+.25*content+120000*style+10*palette+.01*tv
            if not torch.isfinite(loss):raise FloatingPointError('nonfinite loss')
            loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5);opt.step()
            lr=.00008 if model.qat else .0002+.0018*(1-step/a.steps)
            for group in opt.param_groups:group['lr']=lr
            seconds=elapsed+time.monotonic()-t0
            writer.writerow([step+1,float(loss.detach()),float(distill.detach()),float(gradient.detach()),float(content.detach()),float(style.detach()),seconds,model.qat])
            if (step+1)%100==0 or step+1==a.steps:
                meta=dict(step=step+1,total_steps=a.steps,elapsed_seconds=seconds,training_size=a.size,batch=a.batch,source_hashes=source_hashes,teacher_hashes=teacher.hashes,full_resolution=True)
                save(run/'latest.pt',model,opt,meta)
                if not model.qat:save(run/'float.pt',model,opt,meta)
                status=dict(meta,loss=float(loss.detach()),distill=float(distill.detach()),qat=model.qat)
                (run/'status.json').write_text(json.dumps(status,indent=2),encoding='utf-8');f.flush()
                print('TRAIN',step+1,'/',a.steps,'loss',round(float(loss.detach()),4),'L1',round(float(distill.detach()),4),'seconds',round(seconds),'QAT',model.qat,flush=True)
        save(run/'model.pt',model,opt,meta)
        (run/'complete.json').write_text(json.dumps(status,indent=2),encoding='utf-8')


if __name__=='__main__':main()
