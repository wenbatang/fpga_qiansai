"""Independent paint-reference/QAT experiment; never overwrites signed models.

Restore the four painted branches as warm starts, then optimize actual paint
statistics instead of strongly regressing smoothed C8 pixels. Ten-slot order
and the full-resolution C6 arithmetic remain unchanged.
"""
from pathlib import Path
import argparse,csv,hashlib,importlib.util,json,random,sys,time
import numpy as np
from PIL import Image,ImageOps
import torch
from torch.nn import functional as F
from torchvision.transforms.functional import to_tensor
from catalog import ROOT,WS,CATALOG
from hardware_qat import load
from train import atomic,augment,teachers
import teacher_integer

sys.path.append(str(ROOT.parent))
from style_network import load_network
spec=importlib.util.spec_from_file_location('paint_vgg_definition',ROOT.parent/'full720_style/train.py')
vm=importlib.util.module_from_spec(spec);spec.loader.exec_module(vm)
VGG=vm.VGG;gram=vm.gram
VGG_PATH=Path(torch.hub.get_dir())/'checkpoints/vgg19-dcbb9e9d.pth'
PAINT=ROOT.parent/'painterly_style'
RESTORE={0:0,2:1,3:2,4:3}
NAMES=['vangogh','papercut','comic','inkwash']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def moments(y):
 dx=(y[:,:,:,1:]-y[:,:,:,:-1]).abs();dy=(y[:,:,1:]-y[:,:,:-1]).abs()
 return [F.avg_pool2d(z,8) for z in [dx,dy]]
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',default='ten_painterly_v1');p.add_argument('--steps',type=int,default=12000)
 p.add_argument('--batch',type=int,default=4);p.add_argument('--size',type=int,default=144)
 p.add_argument('--source',type=Path);p.add_argument('--slots',type=int,nargs='+');a=p.parse_args()
 torch.set_num_threads(4);torch.backends.cudnn.benchmark=True
 torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
 random.seed(20261102);np.random.seed(20261102);torch.manual_seed(20261102)
 source=a.source or ROOT/'runs/ten_c6_texture_v1/model.pt'
 model,meta=load(source,'cuda');model.train();model.freeze_bn()
 run=ROOT/'runs'/a.run;run.mkdir(parents=True,exist_ok=True);assert not (run/'launch.json').exists(),'Existing experiment preserved'
 old=PAINT/'runs/paint_final/model.pt';old_meta=torch.load(old,map_location='cpu',weights_only=True)
 if a.source is None:
  for target,previous in RESTORE.items():
   prefix=f'branches.{previous}.'
   model.branches[target].load_state_dict({k[len(prefix):]:v for k,v in old_meta['model'].items() if k.startswith(prefix)})
 model.project()
 split_path=ROOT/'runs/ten_c6_v2/split.json';split=json.loads(split_path.read_text(encoding='utf-8'))
 excluded=set(split['user_images_sha256'].values())
 assert set(split['training']).isdisjoint(split['validation'])
 assert all(sha(p) not in excluded for p in split['training'])
 (run/'split.json').write_text(json.dumps(split,ensure_ascii=False,indent=2),encoding='utf-8')
 cache=[]
 for filename in split['training']:
  with Image.open(filename) as image:cache.append(to_tensor(ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'),(176,176),Image.Resampling.LANCZOS)))
 cache=torch.stack(cache).cuda();vgg=VGG().cuda().eval();refs=[];references={};paint_teachers={}
 for record in CATALOG:
  slot=record['slot'];path=WS/'style_model/styles'/(record['name']+'.jpg')
  if slot in RESTORE:path=ROOT.parent/'styles/art6_v1'/(NAMES[RESTORE[slot]]+'.jpg')
  with Image.open(path) as image:ref=to_tensor(ImageOps.fit(image.convert('RGB'),(384,384),Image.Resampling.LANCZOS))[None].cuda()
  with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):refs.append([gram(z) for z in vgg(ref)])
  references[str(path)]=sha(path)
  if slot in RESTORE:
   path=PAINT/'runs/paint_v1/teachers'/NAMES[RESTORE[slot]]/'model.pt'
   t,_=load_network(path,'cuda');t.requires_grad_(False).eval();paint_teachers[slot]=t;references[str(path)]=sha(path)
 c8,c8_hashes=teachers()
 files=[Path(__file__),ROOT/'network.py',ROOT/'hardware_qat.py',ROOT/'integer.py',ROOT/'train.py',ROOT/'teacher_integer.py',ROOT/'catalog.py',ROOT.parent/'full720_style/network.py',ROOT.parent/'full720_style/train.py',ROOT.parent/'style_network.py',VGG_PATH,source,old,split_path]
 hashes={str(path):sha(path) for path in files}
 launch=dict(source=str(source),source_sha256=sha(source),paint_warm_start=str(old) if a.source is None else None,
  steps=a.steps,batch=a.batch,size=a.size,reference_hashes=references,source_hashes=hashes,c8_teacher_hashes=c8_hashes,
  restored_slots=RESTORE,scope='Actual painting VGG statistics plus four high-capacity painting teachers; six C8 outputs are weak spatial anchors only. Independent C6/full resolution/hardware arithmetic QAT.',training_images=512,validation_images=24,user_images_excluded=34)
 (run/'launch.json').write_text(json.dumps(launch,ensure_ascii=False,indent=2),encoding='utf-8')
 # Van Gogh gets four visits per complete schedule to prioritize the reported
 # failure, while the other nine remain independently trained.
 schedule=a.slots or [0,1,0,2,3,0,4,5,6,0,7,8,9]
 opt=torch.optim.Adam(model.parameters(),lr=.000055);started=time.monotonic();visits=[0]*10
 def checkpoint(step):
  return dict(meta,family='ten_independent_full_c6',model={k:v.detach().cpu() for k,v in model.state_dict().items()},
   step=meta['step']+step,refinement_steps=step,hardware_qat=True,qat=True,source_hashes=hashes,
   reference_hashes=references,teacher_hashes=c8_hashes,painting_teachers=True,teacher_is_c8=False,
   elapsed_seconds=time.monotonic()-started,full_resolution=True,student_pool=False,independent_styles=True,training_visits=visits.copy())
 atomic(run/'initial.pt',checkpoint(0))
 with (run/'training.csv').open('w',newline='') as stream:
  writer=csv.writer(stream);writer.writerow(['step','slot','loss','distill','style','texture_energy','content','seconds'])
  for step in range(a.steps):
   slot=schedule[step%len(schedule)];visits[slot]+=1;x=augment(cache,a.size,a.batch)
   with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):
    target=paint_teachers[slot](x).float().clamp(0,1) if slot in paint_teachers else teacher_integer.integer_torch((x*255).round(),c8[slot])/255
    content_target=vgg(x)[2].float();target_energy=moments(target)
   opt.zero_grad(set_to_none=True);y=model(x,slot)
   with torch.autocast('cuda',dtype=torch.bfloat16):
    features=vgg(y);style=sum(F.mse_loss(gram(z),g) for z,g in zip(features,refs[slot]))
    content=F.mse_loss(features[2].float(),content_target)
   distill=F.l1_loss(y,target);coarse=F.l1_loss(F.avg_pool2d(y,8),F.avg_pool2d(target,8))
   energy=sum(F.l1_loss(torch.log(z+.012),torch.log(g+.012)) for z,g in zip(moments(y),target_energy))
   tv=(y[:,:,1:]-y[:,:,:-1]).abs().mean()+(y[:,:,:,1:]-y[:,:,:,:-1]).abs().mean()
   # Pixel regression is deliberately weaker than the former 5*L1+3*coarse.
   loss=.8*distill+coarse+.12*content+220000*style+.25*energy+.025*tv
   if slot==4:
    chroma=(y-y.mean(1,keepdim=True)).abs().mean();loss=loss+2*chroma
   assert torch.isfinite(loss);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),4)
   opt.step();model.project(style=slot)
   elapsed=time.monotonic()-started
   writer.writerow([step+1,slot,float(loss.detach()),float(distill.detach()),float(style.detach()),float(energy.detach()),float(content.detach()),elapsed])
   if (step+1)%250==0 or step+1==a.steps:
    data=checkpoint(step+1);atomic(run/'latest.pt',data);atomic(run/f'step_{step+1:05d}.pt',data)
    status=dict(step=step+1,total=a.steps,slot=slot,loss=float(loss.detach()),style=float(style.detach()),seconds=elapsed,visits=visits)
    (run/'status.json').write_text(json.dumps(status,indent=2),encoding='utf-8');stream.flush();print('PAINTERLY',status,flush=True)
 atomic(run/'model.pt',data)
 (run/'complete.json').write_text(json.dumps(dict(result='PASS',steps=a.steps,visits=visits,elapsed_seconds=elapsed,source_hashes=hashes,reference_hashes=references),ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
