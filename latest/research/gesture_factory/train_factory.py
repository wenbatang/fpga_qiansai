"""Person-disjoint tiny canonical-shape classifier; real-photo test stays held out."""
from pathlib import Path
import argparse,hashlib,json,random,time
import cv2,numpy as np,torch
from torch import nn
from torch.nn import functional as F
ROOT=Path(__file__).resolve().parent
class Network(nn.Module):
 def __init__(self):
  super().__init__();self.layers=nn.ModuleList([nn.Conv2d(1,8,3,2,1),nn.Conv2d(8,12,3,2,1),nn.Conv2d(12,12,3,2,1,groups=12),nn.Linear(192,32),nn.Linear(32,11)])
 def forward(self,x):
  for i,l in enumerate(self.layers):
   if i==3:x=x.flatten(1)
   x=l(x)
   if i!=4:x=F.relu(x)
  return x
def canonical(rgb,mask):
 # Oracle masks isolate the hand; production background extraction needs its
 # own tests. This dataset is NOT proof that board segmentation will work.
 n,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
 if n<2:return None
 k=1+np.argmax(stats[1:,4]);mask=labels==k;ys,xs=np.nonzero(mask);count=len(xs)
 if count<24:return None
 gray=(rgb[:,:,0].astype(np.int32)+2*rgb[:,:,1].astype(np.int32)+rgb[:,:,2].astype(np.int32))//4
 vals=np.sort(gray[mask]);lo=vals[count//20];hi=vals[count*19//20]
 side=max(xs.max()-xs.min()+1,ys.max()-ys.min()+1);side+=(side+7)//8;left=(int(xs.min())+int(xs.max())+1-side)//2;top=(int(ys.min())+int(ys.max())+1-side)//2
 xx=left+((2*np.arange(64)+1)*side)//128;yy=top+((2*np.arange(64)+1)*side)//128
 valid=(yy[:,None]>=0)&(yy[:,None]<64)&(xx[None,:]>=0)&(xx[None,:]<64);yy=yy.clip(0,63);xx=xx.clip(0,63)
 inside=valid&mask[yy[:,None],xx[None,:]];can=np.where(inside,160 if hi-lo<8 else 63+(np.clip(gray[yy[:,None],xx[None,:]],lo,hi)-lo)*192//max(1,hi-lo),0).astype(np.uint8)
 return can
def data():
 p=ROOT/'build/canonical.npz'
 if not p.exists():
  archive=np.load(ROOT/'build/factory_masks.npz');a={k:archive[k] for k in archive.files};images=[];labels=[];splits=[];persons=[];indices=[]
  for i in range(len(a['labels'])):
   image=canonical(a['rgb'][i],a['mask'][i])
   if image is None:continue
   images.append(image);labels.append(a['labels'][i]);splits.append(a['split'][i]);persons.append(a['persons'][i]);indices.append(i)
  np.savez_compressed(p,images=np.array(images),labels=np.array(labels),split=np.array(splits),persons=np.array(persons),indices=np.array(indices))
 return np.load(p)
def augment(x):
 n=x.shape[0];angle=(torch.rand(n,device=x.device)-.5)*.45;scale=.9+torch.rand(n,device=x.device)*.2;flip=torch.where(torch.rand(n,device=x.device)<.5,-1.,1.);theta=torch.zeros(n,2,3,device=x.device)
 theta[:,0,0]=angle.cos()*scale*flip;theta[:,0,1]=-angle.sin()*scale;theta[:,1,0]=angle.sin()*scale*flip;theta[:,1,1]=angle.cos()*scale;theta[:,:,2]=(torch.rand(n,2,device=x.device)-.5)*.12
 x=F.grid_sample(x,F.affine_grid(theta,x.shape,align_corners=False),align_corners=False)
 # Keep background at zero while perturbing illumination/texture.
 x=(x*(.75+torch.rand(n,1,1,1,device=x.device)*.5)+torch.randn_like(x)*.025*(x>.05)).clamp(0,1)
 return x
@torch.no_grad()
def evaluate(model,x,y,indices):
 logits=torch.cat([model(x[b]) for b in indices.split(256)]);truth=y[indices];pred=logits.argmax(1);conf=logits.softmax(1).max(1).values
 matrix=torch.bincount(truth*11+pred,minlength=121).reshape(11,11).cpu().tolist()
 return dict(accuracy=float((pred==truth).float().mean()),per_class=[float((pred[truth==k]==k).float().mean()) if (truth==k).any() else None for k in range(11)],confusion=matrix,confidence_median=float(conf.median()))
def main():
 p=argparse.ArgumentParser();p.add_argument('--steps',type=int,default=6000);a=p.parse_args();torch.set_num_threads(4);cv2.setNumThreads(1);torch.manual_seed(20261102);np.random.seed(20261102);random.seed(20261102)
 ds=data();device='cuda' if torch.cuda.is_available() else 'cpu';x=torch.tensor(ds['images'][:,None,::2,::2]/255,dtype=torch.float32,device=device);y=torch.tensor(ds['labels'],dtype=torch.long,device=device)
 ids={s:torch.tensor(np.flatnonzero(ds['split']==s),device=device) for s in ['train','val','test']}
 # Explicit split leakage checks across both source datasets.
 persons={s:set(ds['persons'][ds['split']==s]) for s in ids};assert not (persons['train']&persons['val'] or persons['train']&persons['test'] or persons['val']&persons['test'])
 classes=[ids['train'][y[ids['train']]==k] for k in range(11)];assert all(len(z) for z in classes),[len(z) for z in classes]
 model=Network().to(device);optimizer=torch.optim.AdamW(model.parameters(),lr=.002,weight_decay=.005);best=-1;out=ROOT/'runs/cnn_v1';out.mkdir(parents=True,exist_ok=True);t=time.monotonic();history=[]
 for step in range(a.steps):
  model.train();labels=torch.randint(0,11,(128,),device=device);batch=torch.stack([classes[int(k)][torch.randint(len(classes[int(k)]),(1,),device=device)[0]] for k in labels]);xx=augment(x[batch]);loss=F.cross_entropy(model(xx),y[batch],label_smoothing=.03);optimizer.zero_grad();loss.backward();optimizer.step()
  for g in optimizer.param_groups:g['lr']=.002*(.08+.92*(1+np.cos(np.pi*(step+1)/a.steps))/2)
  if (step+1)%200==0:
   model.eval();val=evaluate(model,x,y,ids['val']);row=dict(step=step+1,loss=float(loss.detach()),validation=val,seconds=round(time.monotonic()-t));history.append(row);print(step+1,round(float(loss.detach()),3),'val',round(val['accuracy'],4),'classes',[round(z,2) if z is not None else None for z in val['per_class']],'s',row['seconds'],flush=True)
   if val['accuracy']>best:best=val['accuracy'];torch.save(dict(model=model.cpu().state_dict(),step=step+1,validation=val),out/'best.pt');model.to(device)
 checkpoint=torch.load(out/'best.pt',map_location=device,weights_only=False);model.load_state_dict(checkpoint['model']);model.eval();result=dict(result='MEASURED',parameters=sum(p.numel() for p in model.parameters()),step=checkpoint['step'],train=evaluate(model,x,y,ids['train']),validation=evaluate(model,x,y,ids['val']),test=evaluate(model,x,y,ids['test']),counts={s:[int((y[ids[s]]==k).sum()) for k in range(11)] for s in ids},source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'gesture_spec.py',ROOT/'build/factory_masks.npz']},limitation='Offline teacher masks. No physical camera or board accuracy claim.')
 (out/'metrics.json').write_text(json.dumps(result,indent=2),encoding='utf-8');(out/'history.json').write_text(json.dumps(history,indent=2),encoding='utf-8');print('FINAL',result,flush=True)
if __name__=='__main__':main()
