"""Paint-reference teachers and independent, full720 INT8 students. No C8 targets."""
from pathlib import Path
import argparse,csv,hashlib,json,os,random,sys,time
import numpy as np
from PIL import Image,ImageOps
import torch
from torch.nn import functional as F
from torchvision.transforms.functional import to_tensor
ROOT=Path(__file__).resolve().parent;PY=ROOT.parent;WS=PY.parent
sys.path.append(str(PY))
from style_network import load_network
from network import FullStyle,rgb565,BASE
import importlib.util
spec=importlib.util.spec_from_file_location('full_vgg_source',PY/'full720_style/train.py');vgg_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(vgg_module)
VGG=vgg_module.VGG;gram=vgg_module.gram
NAMES=['vangogh','papercut','comic','inkwash']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def atomic(path,data):
    temporary=path.with_suffix('.tmp');torch.save(data,temporary);os.replace(temporary,path)
def augment(x):
    if random.random()<.5:x=x.flip(-1)
    gain=torch.empty(len(x),1,1,1,device=x.device).uniform_(.45,1.35)
    gamma=random.uniform(.75,1.35);x=(x*gain).clamp(0,1).pow(gamma)
    if random.random()<.35:
        # Bright displays/windows and high-key paper belong in training, not validation.
        x=x.clone();h,w=x.shape[-2:];x[:len(x)//2,:,h//4:3*h//4,w//4:3*w//4]=random.uniform(.85,1.)
    return rgb565(x)
def regularizers(y,x,ink):
    tv=(y[:,:,1:]-y[:,:,:-1]).abs().mean()+(y[:,:,:,1:]-y[:,:,:,:-1]).abs().mean()
    if not ink:return tv,y.new_zeros(())
    luma=(x*x.new_tensor([.2126,.7152,.0722])[None,:,None,None]).sum(1,keepdim=True)
    smooth=F.avg_pool2d(luma,9,1,4);edge=(luma-smooth).abs();mask=((luma-.78)/.18).clamp(0,1)*(1-edge*15).clamp(0,1)
    paper=((1-y)*mask).sum()/(mask.sum()*3+1)
    chroma=(y-y.mean(1,keepdim=True)).abs().mean()
    return tv,paper+2*chroma
def state(model,step,elapsed,extra):
    return dict(family='independent_full_c6',config=model.config,model={k:v.detach().cpu() for k,v in model.state_dict().items()},qat=model.qat,step=step,elapsed_seconds=elapsed,**extra)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--teacher-steps',type=int,default=1600);parser.add_argument('--student-steps',type=int,default=14000);parser.add_argument('--size',type=int,default=160);parser.add_argument('--batch',type=int,default=12);parser.add_argument('--run',default='paint_v1');a=parser.parse_args()
    assert torch.cuda.is_available() and a.batch%4==0
    run=ROOT/'runs'/a.run;run.mkdir(parents=True,exist_ok=True);assert not (run/'launch.json').exists(),'Existing run preserved'
    random.seed(20261031);np.random.seed(20261031);torch.manual_seed(20261031);torch.set_num_threads(4)
    torch.backends.cudnn.benchmark=True;torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
    source_files=[Path(__file__),ROOT/'network.py',BASE,PY/'style_network.py',PY/'full720_style/train.py']
    sources={str(p):sha(p) for p in source_files}
    split=json.loads((PY/'full720_style/runs/c6_v1/split.json').read_text(encoding='utf-8'));(run/'split.json').write_text(json.dumps(split,indent=2),encoding='utf-8')
    cached=[]
    for filename in split['training']:
        with Image.open(filename) as image:cached.append(to_tensor(ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'),(a.size,a.size),Image.Resampling.LANCZOS)))
    cache=torch.stack(cached).cuda();vgg=VGG().cuda().eval();teachers=[];references=[];teacher_inputs={}
    for name in NAMES:
        source=PY/'runs/art6_v2/teacher'/name/'model.pt';model,meta=load_network(source,'cuda');teacher_inputs[str(source)]=sha(source)
        path=PY/'styles/art6_v1'/(name+'.jpg');teacher_inputs[str(path)]=sha(path)
        with Image.open(path) as image:reference=to_tensor(ImageOps.fit(image.convert('RGB'),(384,384),Image.Resampling.LANCZOS))[None].cuda()
        with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):targets=[gram(z) for z in vgg(reference)]
        references.append(targets);teachers.append((model,meta))
    launch=dict(source_hashes=sources,teacher_inputs=teacher_inputs,training_images=len(cache),size=a.size,batch=a.batch,teacher_steps=a.teacher_steps,student_steps=a.student_steps,downsample=False,independent_styles=True,teacher_is_c8=False)
    (run/'launch.json').write_text(json.dumps(launch,indent=2),encoding='utf-8')
    t0=time.monotonic()
    for slot,(teacher,meta) in enumerate(teachers):
        folder=run/'teachers'/NAMES[slot];folder.mkdir(parents=True,exist_ok=True)
        opt=torch.optim.Adam(teacher.parameters(),lr=.00008);teacher.train();ink=slot==3
        for step in range(a.teacher_steps):
            x=augment(cache[torch.randint(len(cache),(8,),device='cuda')]);opt.zero_grad(set_to_none=True)
            with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):content_target=vgg(F.avg_pool2d(x,2))[2].float()
            with torch.autocast('cuda',dtype=torch.bfloat16):
                y=teacher(x);features=vgg(y);content=F.mse_loss(vgg(F.avg_pool2d(y,2))[2].float(),content_target)
                style=sum(F.mse_loss(gram(z),target) for z,target in zip(features,references[slot]));tv,paper=regularizers(y,x,ink)
                loss=.45*content+(160000 if ink else 260000)*style+.10*tv+(6 if ink else 0)*paper
            assert torch.isfinite(loss);loss.backward();torch.nn.utils.clip_grad_norm_(teacher.parameters(),5);opt.step()
            if (step+1)%200==0:print('TEACHER',NAMES[slot],step+1,'loss',round(float(loss.detach()),4),'seconds',round(time.monotonic()-t0),flush=True)
        atomic(folder/'model.pt',dict(meta,model={k:v.detach().cpu() for k,v in teacher.state_dict().items()},retrained_steps=a.teacher_steps,source_hashes=sources,reference_sha256=sha(PY/'styles/art6_v1'/(NAMES[slot]+'.jpg'))))
        teacher.eval().requires_grad_(False)
    model=FullStyle().cuda();opt=torch.optim.Adam(model.parameters(),lr=.0012)
    # Starting from the earlier student is a warm start, never an output target.
    old=torch.load(PY/'full720_style/runs/c6_v1/model.pt',map_location='cpu',weights_only=True)
    for slot,branch in enumerate(model.branches):
        values={k:(v[slot:slot+1] if '.affine.weight' in k else v) for k,v in old['model'].items()};branch.load_state_dict(values)
    with (run/'training.csv').open('w',newline='') as log:
        writer=csv.writer(log);writer.writerow(['step','loss','distill','style','paper','seconds','qat'])
        for step in range(a.student_steps):
            if step>=800:model.freeze_bn()
            model.qat=step>=int(a.student_steps*.78);model.train()
            styles=torch.arange(a.batch,device='cuda')%4;x=augment(cache[torch.randint(len(cache),(a.batch,),device='cuda')])
            with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):
                target=torch.cat([teachers[s%4][0](x[s:s+1]) for s in range(a.batch)]);original=vgg(F.avg_pool2d(x,2))[2].float()
            opt.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16):
                y=model(x,styles);features=vgg(y)
                distill=F.l1_loss(y,target);coarse=F.l1_loss(F.avg_pool2d(y,4),F.avg_pool2d(target,4))
                content=F.mse_loss(vgg(F.avg_pool2d(y,2))[2].float(),original)
                style=y.new_zeros(())
                for slot in range(4):
                    ids=styles==slot;style+=sum(F.mse_loss(gram(z[ids]),g.expand(int(ids.sum()),-1,-1)) for z,g in zip(features,references[slot]))/4
                tv,_=regularizers(y,x,False);_,paper=regularizers(y[styles==3],x[styles==3],True)
                # Strong reference texture; no high-weight teacher edge or pixel-copy loss.
                loss=3*distill+4*coarse+.18*content+180000*style+.08*tv+5*paper
            if not torch.isfinite(loss):raise FloatingPointError('nonfinite student loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),4);opt.step()
            lr=.000045 if model.qat else .0001+.0011*(1-step/a.student_steps)
            for group in opt.param_groups:group['lr']=lr
            elapsed=time.monotonic()-t0;writer.writerow([step+1,float(loss.detach()),float(distill.detach()),float(style.detach()),float(paper.detach()),elapsed,model.qat])
            if (step+1)%500==0 or step+1==a.student_steps:
                extra=dict(source_hashes=sources,teacher_inputs=teacher_inputs,full_resolution=True,independent_styles=True,training_size=a.size,training_images=len(cache),batch=a.batch)
                checkpoint=state(model,step+1,elapsed,extra);atomic(run/'latest.pt',checkpoint)
                if not model.qat:atomic(run/'float.pt',checkpoint)
                (run/'status.json').write_text(json.dumps(dict(step=step+1,loss=float(loss.detach()),distill=float(distill.detach()),paper=float(paper.detach()),seconds=elapsed,qat=model.qat),indent=2),encoding='utf-8');log.flush()
                print('STUDENT',step+1,'loss',round(float(loss.detach()),4),'paper',round(float(paper.detach()),3),'seconds',round(elapsed),'QAT',model.qat,flush=True)
        atomic(run/'model.pt',checkpoint);(run/'complete.json').write_text(json.dumps(dict(step=a.student_steps,elapsed_seconds=time.monotonic()-t0,source_hashes=sources,full_resolution=True,independent_styles=True),indent=2),encoding='utf-8')


if __name__=='__main__':main()
