"""Six learned teachers and larger int8 students; no hardware programming.

Style emphasis is perceptual/multiscale texture, with restrained palette loss.
The hardware student has eight channels and a 63x63 receptive field without
absolute coordinate channels. Existing models and releases are never replaced.
"""
from pathlib import Path
import argparse,csv,json,math,random,time
import numpy as np
import torch
from PIL import Image,ImageOps
from torch.nn import functional as F
from torch.utils.data import DataLoader
from torchvision.transforms.functional import to_tensor
from art6_catalog import ROOT,REF,RUN,STYLES,sha
from style_network import load_network
from hardware_network import HardwareNetwork,rgb565_roundtrip
from train_style import ContentDataset,VGGFeatures,gram,seed_worker
from train_optimized import variation,palette_quantiles,save
from export_hardware import export

def perceptual(vgg,y,x,targets,palette):
 features=vgg(y);content=F.mse_loss(features[2].float(),x)
 style=sum(F.mse_loss(gram(f),t.expand(len(y),-1,-1)) for f,t in zip(features,targets))
 color=F.mse_loss(palette_quantiles(y),palette.expand(len(y),-1,-1))
 return content,style,color

def train(name,stage,args,split,vgg,device):
 folder=RUN/stage/name
 if (folder/'experiment.json').exists():
  print('PRESERVE COMPLETED',stage,name,flush=True);return
 if (folder/'model.pt').exists():raise FileExistsError('Incomplete run preserved: '+str(folder))
 folder.mkdir(parents=True,exist_ok=True)
 seed=20261018+list(STYLES).index(name);random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
 mono=STYLES[name]['monochrome']
 warm=ROOT/'runs/distinct_teacher_v2'/STYLES[name]['warm']/'model.pt'
 teacher_path=warm if stage=='teacher' else RUN/'teacher'/name/'model.pt'
 teacher,_=load_network(teacher_path,device)
 model=teacher if stage=='teacher' else HardwareNetwork(channels=12,monochrome=mono,depth=5,coordinate_phase=0,dilations=[1,2,4,8,16]).to(device)
 if stage=='student':teacher.requires_grad_(False)
 ref=Image.open(REF/(name+'.jpg')).convert('RGB');ref.thumbnail((512,512))
 with torch.no_grad():
  reference=to_tensor(ref)[None].to(device);targets=[gram(f) for f in vgg(reference)];palette=palette_quantiles(reference)
 size=256 if stage=='teacher' else 192
 epochs=args.teacher_epochs if stage=='teacher' else args.student_epochs
 loader=DataLoader(ContentDataset(ROOT/'convertpic/val2017',split['training'],size),batch_size=12,
  shuffle=True,num_workers=2,persistent_workers=True,pin_memory=True,worker_init_fn=seed_worker,generator=torch.Generator().manual_seed(seed))
 validation=[]
 for file in split['validation'][:18]:
  with Image.open(ROOT/'convertpic/val2017'/file) as im:
   validation.append(to_tensor(ImageOps.fit(ImageOps.exif_transpose(im).convert('RGB'),(size,size),Image.Resampling.LANCZOS)))
 style_weight={'vangogh':240000.,'monet':180000.,'ukiyoe':200000.,'papercut':180000.,'comic':180000.,'inkwash':150000.}[name]
 palette_weight=12. if name!='inkwash' else 3.
 content_weight=.7 if stage=='teacher' else .5
 optimizer=torch.optim.Adam(model.parameters(),lr=.0002 if stage=='teacher' else .001)
 scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,epochs,eta_min=.000025)
 meta={'style':name,'label':STYLES[name]['label'],'generation':RUN.name,'family':'perceptual_teacher' if stage=='teacher' else 'dilated_int8_student',
  'seed':seed,'style_sha256':sha(REF/(name+'.jpg')),'teacher_sha256':sha(teacher_path),'parameters':sum(p.numel() for p in model.parameters()),
  'training_images':len(split['training']),'validation_names':split['validation'][:18],
  'training_size':size,'epochs':epochs,'palette_weight':palette_weight,'style_weight':style_weight,
  'content_weight':content_weight,'coordinate_features':False,'purpose':'Xilinx six-style experiment; no claimed physical performance'}
 step=0;best=math.inf;began=time.monotonic()
 with (folder/'training.csv').open('w',newline='') as file:
  writer=csv.writer(file);writer.writerow(['epoch','step','loss','content','style','distill','seconds'])
  for epoch in range(epochs):
   model.train()
   if stage=='student' and epoch>=max(6,epochs//2):
    if not model.qat:
     model.freeze_bn();model.qat=True;model.straight_through_clip=False
     # Preserve a known starting point before any quantized update. The first
     # experiment's high-LR STE clipping collapsed content and is archived.
     save(folder/'qat_initial.pt',model,{**meta,'epoch':epoch,'step':step,'qat':True})
     for group in optimizer.param_groups:group['lr']*=.1
   for x in loader:
    x=x.to(device,non_blocking=True)
    if stage=='student':x=rgb565_roundtrip(x)
    optimizer.zero_grad(set_to_none=True)
    with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):
     original=vgg(x)[2].float();desired=teacher(x) if stage=='student' else None
    y=model(x)
    with torch.autocast('cuda',dtype=torch.bfloat16):content,style,color=perceptual(vgg,y,original,targets,palette)
    distill=F.l1_loss(y,desired) if desired is not None else y.new_zeros(())
    # Match the teacher at two spatial scales without forcing its color
    # histogram to dominate brush/shape changes.
    coarse=F.l1_loss(F.avg_pool2d(y,4),F.avg_pool2d(desired,4)) if desired is not None else y.new_zeros(())
    loss=content_weight*content+style_weight*style+palette_weight*color+.04*variation(y)+20*distill+10*coarse
    if not torch.isfinite(loss):raise FloatingPointError(name)
    loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);optimizer.step();step+=1
    writer.writerow([epoch+1,step,float(loss.detach()),float(content.detach()),float(style.detach()),float(distill.detach()),time.monotonic()-began])
   scheduler.step();model.eval();scores=[]
   with torch.inference_mode():
    for offset in range(0,len(validation),6):
     x=torch.stack(validation[offset:offset+6]).to(device)
     if stage=='student':x=rgb565_roundtrip(x)
     y=model(x);original=vgg(x)[2];c,s,p=perceptual(vgg,y,original,targets,palette)
     d=F.l1_loss(y,teacher(x)) if stage=='student' else y.new_zeros(())
     scores.append([float(c),float(s),float(p),float(d)])
   c,s,p,d=np.mean(scores,axis=0).tolist();objective=content_weight*c+style_weight*s+palette_weight*p+20*d
   current={**meta,'epoch':epoch+1,'step':step,'elapsed_seconds':time.monotonic()-began,'qat':bool(getattr(model,'qat',False)),
    'validation':{'content':c,'style':s,'palette':p,'teacher_l1':d,'objective':objective}}
   save(folder/'latest.pt',model,current)
   if stage=='student' and not model.qat:
    save(folder/'float_latest.pt',model,current)
   if (stage=='teacher' or model.qat) and objective<best:
    best=objective;save(folder/'model.pt',model,current)
   file.flush();print('VALID',stage,name,epoch+1,'step',step,'objective',round(objective,4),'best',round(best,4),'seconds',round(time.monotonic()-began),flush=True)
  (folder/'experiment.json').write_text(json.dumps({**current,'best_objective':best},ensure_ascii=False,indent=2),encoding='utf-8')
 if stage=='student':export(folder/'model.pt',RUN/'export'/name)
 del model,teacher,optimizer,loader;torch.cuda.empty_cache()

def main():
 p=argparse.ArgumentParser();p.add_argument('--teacher-epochs',type=int,default=10);p.add_argument('--student-epochs',type=int,default=20)
 p.add_argument('--style',nargs='+',choices=list(STYLES),default=list(STYLES));a=p.parse_args()
 if min(a.teacher_epochs,a.student_epochs)<6:raise ValueError('At least six epochs for QAT schedule')
 assert torch.cuda.is_available();torch.set_num_threads(4);torch.backends.cudnn.benchmark=True
 torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
 RUN.mkdir(parents=True,exist_ok=True)
 split=json.loads((ROOT/'runs/four_styles_v1/split.json').read_text());assert not set(split['training'])&set(split['validation'])
 (RUN/'split.json').write_text(json.dumps(split,indent=2))
 vgg=VGGFeatures(Path.home()/'.cache/torch/hub/checkpoints/vgg19-dcbb9e9d.pth').cuda().eval()
 for name in a.style:
  train(name,'teacher',a,split,vgg,'cuda');train(name,'student',a,split,vgg,'cuda')
 if all((RUN/'student'/name/'experiment.json').exists() for name in STYLES):
  (RUN/'complete.json').write_text(json.dumps({'styles':list(STYLES),'channels':12,'dilations':[1,2,4,8,16],'coordinate_phase':0,'hardware_programmed':False},indent=2))
if __name__=='__main__':main()
