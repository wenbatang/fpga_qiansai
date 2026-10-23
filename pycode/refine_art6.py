"""CPU-only shape/contrast distillation candidates, separate from base training."""
from pathlib import Path
import argparse,json,time
import torch
from PIL import Image,ImageOps
from torchvision.transforms.functional import to_tensor
from torch.utils.data import DataLoader
from torch.nn import functional as F
from art6_catalog import ROOT,RUN,STYLES,sha
from train_style import ContentDataset
from train_optimized import save
from style_network import load_network
from hardware_network import rgb565_roundtrip
from export_hardware import export

def edge_loss(a,b):
 return (F.l1_loss(a[:,:,1:]-a[:,:,:-1],b[:,:,1:]-b[:,:,:-1])+
         F.l1_loss(a[:,:,:,1:]-a[:,:,:,:-1],b[:,:,:,1:]-b[:,:,:,:-1]))/2

def contrast(a,b):
 return F.l1_loss(a.flatten(2).std(dim=2),b.flatten(2).std(dim=2))

@torch.inference_mode()
def score(model,teacher,images,contrast_weight=0.):
 model.eval();values=[]
 for i in range(0,len(images),3):
  x=rgb565_roundtrip(torch.stack(images[i:i+3]));y=model(x);target=teacher(x)
  values.append(float(F.l1_loss(y,target)+.7*F.l1_loss(F.avg_pool2d(y,4),F.avg_pool2d(target,4))+.3*edge_loss(y,target)+contrast_weight*contrast(y,target)))
 return sum(values)/len(values)

def main():
 p=argparse.ArgumentParser();p.add_argument('--style',nargs='+',choices=list(STYLES),default=['papercut','comic'])
 p.add_argument('--limit',type=int,default=512);p.add_argument('--epochs',type=int,default=3)
 p.add_argument('--output',type=Path,default=ROOT/'runs/art6_refine_v1');p.add_argument('--contrast-weight',type=float,default=0.);a=p.parse_args()
 torch.set_num_threads(4);out=a.output;out.mkdir(parents=True,exist_ok=True)
 split=json.loads((RUN/'split.json').read_text());(out/'split.json').write_text(json.dumps(split,indent=2))
 images=[]
 for name in split['validation'][:18]:
  with Image.open(ROOT/'convertpic/val2017'/name) as im:
   images.append(to_tensor(ImageOps.fit(ImageOps.exif_transpose(im).convert('RGB'),(192,192),Image.Resampling.LANCZOS)))
 for name in a.style:
  folder=out/name
  if (folder/'experiment.json').exists():continue
  if folder.exists():raise FileExistsError('Preserve incomplete candidate '+str(folder))
  deadline=time.monotonic()+4*3600
  while not (RUN/'student'/name/'experiment.json').exists():
   if time.monotonic()>deadline:raise TimeoutError(name)
   time.sleep(3)
  folder.mkdir();torch.manual_seed(20261018)
  model,meta=load_network(RUN/'student'/name/'model.pt','cpu')
  teacher,_=load_network(RUN/'teacher'/name/'model.pt','cpu');teacher.requires_grad_(False)
  assert model.qat and model.config['channels']==12
  initial=score(model,teacher,images,a.contrast_weight);best=initial
  record={**{k:v for k,v in meta.items() if k!='model'},'generation':out.name,'base_checkpoint_sha256':sha(RUN/'student'/name/'model.pt'),
   'teacher_sha256':sha(RUN/'teacher'/name/'model.pt'),'refinement_training_names':split['training'][:a.limit],
   'refinement_initial_objective':initial,'refinement_objective':'teacher pixel L1 + 0.7 pooled L1 + 0.3 gradient L1; no palette/Gram loss',
   'refinement_device':'CPU; base GPU experiment independent','refinement_learning_rate':.00015,'refinement_contrast_weight':a.contrast_weight}
  save(folder/'model.pt',model,record)
  loader=DataLoader(ContentDataset(ROOT/'convertpic/val2017',split['training'][:a.limit],192),batch_size=6,
   shuffle=True,num_workers=0,generator=torch.Generator().manual_seed(20261018))
  optim=torch.optim.Adam(model.parameters(),lr=.00015);began=time.monotonic();steps=0
  for epoch in range(a.epochs):
   model.train()
   for x in loader:
    x=rgb565_roundtrip(x)
    with torch.no_grad():target=teacher(x)
    optim.zero_grad(set_to_none=True);y=model(x)
    loss=F.l1_loss(y,target)+.7*F.l1_loss(F.avg_pool2d(y,4),F.avg_pool2d(target,4))+.3*edge_loss(y,target)+a.contrast_weight*contrast(y,target)
    loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1);optim.step();steps+=1
   value=score(model,teacher,images,a.contrast_weight)
   current={**record,'epoch':meta['epoch']+epoch+1,'step':meta['step']+steps,'refinement_epochs':epoch+1,
    'refinement_objective_value':value,'refinement_elapsed_seconds':time.monotonic()-began}
   save(folder/'latest.pt',model,current)
   if value<best:best=value;save(folder/'model.pt',model,current)
   print('REFINE',name,epoch+1,'objective',round(value,5),'initial',round(initial,5),'seconds',round(time.monotonic()-began),flush=True)
  (folder/'experiment.json').write_text(json.dumps({**current,'best_refinement_objective':best},ensure_ascii=False,indent=2),encoding='utf-8')
  export(folder/'model.pt',out/'export'/name)
  print('CANDIDATE COMPLETE',name,flush=True)
if __name__=='__main__':main()
