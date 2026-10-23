"""Actual held-out predictions, integer checks and readable six-style sheets."""
from pathlib import Path
import argparse,hashlib,itertools,json
import numpy as np
import torch
from PIL import Image,ImageDraw,ImageOps
from torchvision.transforms.functional import to_tensor
from art6_catalog import ROOT,RUN,REF,STYLES,sha
from style_network import load_network
from hardware_network import rgb565_roundtrip
from export_hardware import load_export,integer_network
from compare_styles import font,to_image,sheet

@torch.inference_mode()
def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['teacher','student'],default='student')
 p.add_argument('--run',type=Path,default=RUN);p.add_argument('--candidate-root',type=Path)
 p.add_argument('--style',nargs='+',choices=list(STYLES),default=list(STYLES));p.add_argument('--cpu',action='store_true')
 p.add_argument('--allow-partial',action='store_true');p.add_argument('--integer',action='store_true');p.add_argument('--checkpoint',choices=['model.pt','float_latest.pt','qat_initial.pt'],default='model.pt');a=p.parse_args()
 torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
 device='cpu' if a.cpu else 'cuda';out=ROOT/'results'/(a.candidate_root or a.run).name/a.stage
 if a.checkpoint!='model.pt':out=out/a.checkpoint.removesuffix('.pt')
 out.mkdir(parents=True,exist_ok=True)
 split=json.loads((a.run/'split.json').read_text());names=split['validation'][24:36]
 images=[]
 for name in names:
  with Image.open(ROOT/'convertpic/val2017'/name) as im:
   images.append(ImageOps.fit(ImageOps.exif_transpose(im).convert('RGB'),(256,256),Image.Resampling.LANCZOS))
 x=torch.stack([to_tensor(im) for im in images]).to(device)
 if a.stage=='student':x=rgb565_roundtrip(x)
 outputs={};result={'scope':'12 development holdout photographs, disjoint from training and 18 selection images; not a blind final test',
  'stage':a.stage,'names':names,'styles':{},'hardware_measured':False}
 for name in a.style:
  path=(a.candidate_root/name if a.candidate_root else a.run/a.stage/name)/a.checkpoint
  if not path.exists():
   if a.allow_partial:continue
   raise FileNotFoundError(path)
  model,meta=load_network(path,device);y=torch.cat([model(x[i:i+3]) for i in range(0,len(x),3)])
  if a.stage=='student':y=rgb565_roundtrip(y)
  outputs[name]=y.cpu()
  predictions=[to_image(t) for t in y]
  sheet(images,predictions,Image.open(REF/(name+'.jpg')),STYLES[name]['label'],1,1,names).save(out/(name+'_comparison.png'))
  record={'checkpoint_sha256':sha(path),'epoch':meta['epoch'],'training_steps':meta['step'],
   'mean_chroma':float((y.max(1).values-y.min(1).values).mean()),
   'between_photo_l1':float((y[:6]-y[6:12]).abs().mean()),
   'mean_spatial_std':float(y.flatten(2).std(dim=2).mean()),
   'clipped_fraction':float(((y<=0)|(y>=1)).float().mean()),'model_config':model.config}
  if a.integer and a.stage=='student':
   em,layers=load_export((a.candidate_root or a.run)/'export'/name);assert em['checkpoint_sha256']==record['checkpoint_sha256']
   max_error=0;checked=0
   for i in range(3):
    rgb=torch.floor(x[i].permute(1,2,0)*255+.5).cpu().numpy().astype(np.uint8)
    expected=integer_network(rgb,layers,em['monochrome'])
    actual=torch.floor(model(x[i:i+1])[0].permute(1,2,0)*255+.5).cpu().numpy().astype(np.uint8)
    max_error=max(max_error,int(np.abs(expected.astype('int32')-actual.astype('int32')).max()));checked+=actual.size
   assert max_error==0,(name,max_error)
   record.update(integer_max_abs_error=max_error,integer_values_checked=checked)
  result['styles'][name]=record;print(name,record,flush=True)
  del model,y
 if outputs:
  # Same three originals in the first column; all available styles alongside.
  labels=['原图']+[STYLES[n]['label'] for n in outputs];size=220;gap=9;top=75
  canvas=Image.new('RGB',(len(labels)*(size+gap)+gap,top+3*(size+gap)+40),'#f5f3ef');draw=ImageDraw.Draw(canvas)
  draw.text((gap,8),'六风格实际网络输出 · '+('教师' if a.stage=='teacher' else 'RGB565 / 定点学生'),font=font(23),fill='#172b3a')
  for c,label in enumerate(labels):draw.text((gap+c*(size+gap),43),label,font=font(18),fill='#172b3a')
  for row in range(3):
   for c,name in enumerate([None,*outputs]):
    im=images[row] if name is None else to_image(outputs[name][row])
    canvas.paste(im.resize((size,size)),(gap+c*(size+gap),top+row*(size+gap)))
  draw.text((gap,canvas.height-29),'真实训练留出集推理；不是AI概念图，尚未实板验收',font=font(17),fill='#555555')
  canvas.save(out/'six_styles_comparison.png')
  result['pairwise_l1']={left+'/'+right:float((outputs[left]-outputs[right]).abs().mean()) for left,right in itertools.combinations(outputs,2)}
 (out/'evaluation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
