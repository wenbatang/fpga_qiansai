"""Final hardware-arithmetic QAT; folded gain projection avoids invalid shifts."""
from pathlib import Path
import argparse,hashlib,json,sys,time
import torch
from torch.nn import functional as F
from PIL import Image,ImageOps
from torchvision.transforms.functional import to_tensor
from hardware_qat import load
from train import VGG,gram,augment,regularizers,atomic,NAMES
ROOT=Path(__file__).resolve().parent;PY=ROOT.parent
sys.path.append(str(PY));from style_network import load_network


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=ROOT/'runs/paint_v1/model.pt');parser.add_argument('--steps',type=int,default=3000);a=parser.parse_args()
    torch.set_num_threads(4);torch.backends.cudnn.benchmark=True;torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False;torch.manual_seed(20301030)
    run=ROOT/'runs/paint_final';run.mkdir(parents=True,exist_ok=True);assert not (run/'launch.json').exists(),'Final run preserved'
    model,meta=load(a.source,'cuda');changed=model.project();model.train();vgg=VGG().cuda().eval()
    split=json.loads((ROOT/'runs/paint_v1/split.json').read_text(encoding='utf-8'));cached=[]
    for path in split['training']:
        with Image.open(path) as image:cached.append(to_tensor(ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'),(160,160),Image.Resampling.LANCZOS)))
    cache=torch.stack(cached).cuda();teachers=[];targets=[]
    for name in NAMES:
        teacher,_=load_network(ROOT/'runs/paint_v1/teachers'/name/'model.pt','cuda');teacher.requires_grad_(False);teachers.append(teacher)
        with Image.open(PY/'styles/art6_v1'/(name+'.jpg')) as image:reference=to_tensor(ImageOps.fit(image.convert('RGB'),(384,384),Image.Resampling.LANCZOS))[None].cuda()
        with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):targets.append([gram(z) for z in vgg(reference)])
    source_files=[Path(__file__),ROOT/'hardware_qat.py',ROOT/'network.py',ROOT/'integer.py',a.source]
    hashes={**meta['source_hashes'],**{str(p):sha(p) for p in source_files}}
    (run/'launch.json').write_text(json.dumps(dict(source=str(a.source),source_sha256=sha(a.source),steps=a.steps,hardware_qat=True,initial_projected_channels=changed,sources=hashes),indent=2),encoding='utf-8')
    opt=torch.optim.Adam(model.parameters(),lr=.000045);t0=time.monotonic()
    for step in range(a.steps):
        styles=torch.arange(12,device='cuda')%4;x=augment(cache[torch.randint(len(cache),(12,),device='cuda')])
        with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):desired=torch.cat([teachers[s%4](x[s:s+1]) for s in range(12)]);content_target=vgg(F.avg_pool2d(x,2))[2].float()
        opt.zero_grad(set_to_none=True);y=model(x,styles)
        with torch.autocast('cuda',dtype=torch.bfloat16):
            features=vgg(y);style=y.new_zeros(())
            for slot in range(4):
                ids=styles==slot;style+=sum(F.mse_loss(gram(z[ids]),g.expand(int(ids.sum()),-1,-1)) for z,g in zip(features,targets[slot]))/4
            distill=F.l1_loss(y,desired);coarse=F.l1_loss(F.avg_pool2d(y,4),F.avg_pool2d(desired,4));content=F.mse_loss(vgg(F.avg_pool2d(y,2))[2].float(),content_target)
            tv,_=regularizers(y,x,False);_,paper=regularizers(y[styles==3],x[styles==3],True)
            loss=3*distill+4*coarse+.18*content+180000*style+.08*tv+5*paper
        assert torch.isfinite(loss);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),4);opt.step();model.project()
        if (step+1)%250==0 or step+1==a.steps:
            data=dict(meta,model={k:v.detach().cpu() for k,v in model.state_dict().items()},hardware_qat=True,qat=True,source_hashes=hashes,step=meta['step']+step+1,base_step=meta['step'],hardware_qat_step=step+1,clipping_limit=110.,elapsed_seconds=meta['elapsed_seconds']+time.monotonic()-t0)
            atomic(run/'latest.pt',data);(run/'status.json').write_text(json.dumps(dict(step=data['step'],hardware_step=step+1,loss=float(loss.detach()),paper=float(paper.detach()),seconds=time.monotonic()-t0),indent=2),encoding='utf-8')
            print('HARDWARE QAT',step+1,'loss',round(float(loss.detach()),4),'seconds',round(time.monotonic()-t0),flush=True)
    atomic(run/'model.pt',data);(run/'complete.json').write_text(json.dumps(dict(step=data['step'],hardware_qat=True,source_hashes=hashes),indent=2),encoding='utf-8')


if __name__=='__main__':main()
