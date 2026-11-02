"""Second, separate capacity/shape ablation; v1 artifacts stay preserved."""
from pathlib import Path
import argparse,hashlib,json,time
import numpy as np,torch
from torch import nn
from torch.nn import functional as F
from train_factory import data,evaluate,augment
ROOT=Path(__file__).resolve().parent
class Network(nn.Module):
 def __init__(self):
  super().__init__();self.layers=nn.ModuleList([nn.Conv2d(2,12,3,2,1),nn.Conv2d(12,16,3,2,1),nn.Conv2d(16,16,3,2,1,groups=16),nn.Linear(256,40),nn.Linear(40,11)])
 def forward(self,x):
  for i,l in enumerate(self.layers):
   if i==3:x=x.flatten(1)
   x=l(x)
   if i!=4:x=F.relu(x)
  return x
def main():
 p=argparse.ArgumentParser();p.add_argument('--steps',type=int,default=6000);a=p.parse_args();torch.set_num_threads(4);torch.manual_seed(20261103)
 ds=data();device='cuda';gray=torch.tensor(ds['images'][:,None,::2,::2]/255,dtype=torch.float32,device=device);x=torch.cat([gray,(gray>0).float()],1);y=torch.tensor(ds['labels'],dtype=torch.long,device=device)
 ids={s:torch.tensor(np.flatnonzero(ds['split']==s),device=device) for s in ['train','val','test']};classes=[ids['train'][y[ids['train']]==k] for k in range(11)]
 subjects={s:set(ds['persons'][ds['split']==s]) for s in ids};assert all(not(subjects[a]&subjects[b]) for a,b in [('train','val'),('train','test'),('val','test')])
 model=Network().to(device);optimizer=torch.optim.AdamW(model.parameters(),lr=.002,weight_decay=.003);out=ROOT/'runs/cnn_v2';out.mkdir(parents=True,exist_ok=True);best=-1;history=[];start=time.monotonic()
 for step in range(a.steps):
  labels=torch.randint(0,11,(128,),device=device);batch=torch.stack([classes[int(k)][torch.randint(len(classes[int(k)]),(1,),device=device)[0]] for k in labels]);xx=augment(x[batch]);loss=F.cross_entropy(model(xx),y[batch],label_smoothing=.02);optimizer.zero_grad();loss.backward();optimizer.step()
  for g in optimizer.param_groups:g['lr']=.002*(.05+.95*(1+np.cos(np.pi*(step+1)/a.steps))/2)
  if (step+1)%200==0:
   model.eval();v=evaluate(model,x,y,ids['val']);balanced=float(np.mean([z for z in v['per_class'] if z is not None]));print(step+1,'val',round(v['accuracy'],3),'balanced',round(balanced,3),[round(z,2) if z is not None else None for z in v['per_class']],'s',round(time.monotonic()-start),flush=True)
   history.append(dict(step=step+1,validation=v,balanced=balanced))
   if balanced>best:best=balanced;torch.save(dict(model=model.cpu().state_dict(),step=step+1),out/'best.pt');model.to(device)
   model.train()
 ck=torch.load(out/'best.pt',map_location=device,weights_only=False);model.load_state_dict(ck['model']);model.eval();result=dict(result='MEASURED_NOT_DEPLOYED',parameters=sum(p.numel() for p in model.parameters()),step=ck['step'],validation=evaluate(model,x,y,ids['val']),test=evaluate(model,x,y,ids['test']),train=evaluate(model,x,y,ids['train']),counts={s:[int((y[ids[s]]==k).sum()) for k in range(11)] for s in ids},source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'train_factory.py',ROOT/'gesture_spec.py',ROOT/'build/factory_masks.npz']},limitation='Offline teacher masks only. Class7 has no validation support; cannot pass deployment.')
 (out/'metrics.json').write_text(json.dumps(result,indent=2),encoding='utf-8');(out/'history.json').write_text(json.dumps(history,indent=2),encoding='utf-8');print('FINAL val/test',result['validation']['accuracy'],result['test']['accuracy'],flush=True)
if __name__=='__main__':main()
