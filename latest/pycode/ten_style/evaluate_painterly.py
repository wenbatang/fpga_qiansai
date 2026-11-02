"""Real old-ten/old-four/new-model comparisons; isolated output directories."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from PIL import Image,ImageOps,ImageDraw,ImageFont
import torch
from catalog import ROOT,WS,CATALOG
from hardware_qat import FullStyle,load
from integer import model_layers,integer_numpy,integer_torch,prepare_gpu
from network import rgb565
RESTORE={0:0,2:1,3:2,4:3}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def array(y):return y[0].permute(1,2,0).float().clamp(0,255).round().cpu().numpy().astype(np.uint8)
def measure(x,y):
 a=np.concatenate([x.reshape(-1,3)/255,np.ones((x.shape[0]*x.shape[1],1))],1)
 coef=np.linalg.lstsq(a,y.reshape(-1,3)/255,rcond=None)[0]
 spatial=float(np.sqrt(np.square(a@coef-y.reshape(-1,3)/255).mean())*255)
 gray=y.astype(np.float32).mean(2)
 return dict(affine_color_residual_rms=spatial,gradient_energy=float((np.abs(np.diff(gray,axis=0)).mean()+np.abs(np.diff(gray,axis=1)).mean())/2),rgb_mean=y.mean((0,1)).tolist())
def main():
 p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--out',required=True)
 p.add_argument('--quick',action='store_true');p.add_argument('--slots',type=int,nargs='+',default=list(range(10)));p.add_argument('--user',action='store_true');a=p.parse_args()
 folder=ROOT/'results'/a.out;folder.mkdir(parents=True,exist_ok=True)
 assert not (folder/'verification.json').exists(),'Existing comparison preserved'
 torch.set_num_threads(4);torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
 model,meta=load(a.checkpoint,'cuda');old,old_meta=load(ROOT/'runs/ten_c6_texture_v1/model.pt','cuda')
 old_path=ROOT.parent/'painterly_style/runs/paint_final/model.pt';d=torch.load(old_path,map_location='cpu',weights_only=True)
 old4=FullStyle(**d['config']).cuda();old4.load_state_dict(d['model']);old4.freeze_bn();old4.eval()
 split_path=ROOT/'runs/ten_c6_v2/split.json';split=json.loads(split_path.read_text(encoding='utf-8'))
 photos=[Path(split['validation'][i]) for i in [0,6,12]]
 if a.user:photos += [WS/'style_model/images'/name for name in ['0001.png','0005.png']]
 font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',17);size=(512,288) if a.quick else (1280,720)
 records=[];source_paths=[a.checkpoint,old_path,ROOT/'runs/ten_c6_texture_v1/model.pt',Path(__file__),ROOT/'network.py',ROOT/'hardware_qat.py',ROOT/'integer.py',ROOT/'catalog.py',split_path,*photos]
 for photo in photos:
  with Image.open(photo) as image:original=np.asarray(ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'),size,Image.Resampling.LANCZOS)).copy()
  x=rgb565(torch.tensor(original.transpose(2,0,1)[None].astype(np.float32)/255,device='cuda'));raw=(x*255).round();original=array(raw)
  canvas=Image.new('RGB',(1348,55+len(a.slots)*220),'#f5f2eb');draw=ImageDraw.Draw(canvas)
  draw.text((12,8),'实际模型输出：原图 / 当前十风格 / 保留四风格 / 本轮重训'+('（快速预览）' if a.quick else '（完整720p整数）'),font=font,fill='#22334b')
  for row,slot in enumerate(a.slots):
   layers=model_layers(model,slot)
   with torch.no_grad():
    previous=array(old(x,slot)*255);previous4=array(old4(x,RESTORE[slot])*255) if slot in RESTORE else np.full_like(original,245)
    actual=array(model(x,slot)*255) if a.quick else array(integer_torch(raw,prepare_gpu(layers)))
   if not a.quick:
    expected=integer_numpy(original,layers);assert np.array_equal(expected,actual),(photo.name,slot,'int64')
    with torch.no_grad():qat=array(model(x,slot)*255)
    assert np.array_equal(qat,expected),(photo.name,slot,'hardware QAT')
   Image.fromarray(actual).save(folder/f'{photo.stem}_{slot:02d}_new.png')
   if slot==0:Image.fromarray(previous).save(folder/f'{photo.stem}_00_before.png')
   for col,value in enumerate([original,previous,previous4,actual]):canvas.paste(Image.fromarray(value).resize((324,182),Image.Resampling.LANCZOS),(12+col*334,42+row*220))
   draw.text((12,226+row*220),f'{slot} {CATALOG[slot]["label"]}',font=font,fill='#22334b')
   records.append(dict(photo=str(photo),slot=slot,pixels=size[0]*size[1],old=measure(original,previous),new=measure(original,actual),old4=measure(original,previous4) if slot in RESTORE else None,integer_max_abs_error=None if a.quick else 0,qat_max_abs_error=None if a.quick else 0))
  canvas.save(folder/f'{photo.stem}_comparison.png');print('COMPARISON',photo.name,flush=True)
 # Numerical coverage on arbitrary raw uint8 inputs, not only RGB565 photos.
 small=0;maximum=0;clipped=0;shapes=[]
 if not a.quick:
  rng=np.random.default_rng(20261102)
  for slot in range(10):
   layers=model_layers(model,slot);maximum=max(maximum,max(l['bound'] for l in layers));clipped+=sum(l['clipped_weights'] for l in layers)
   for h,w in [(1,1),(5,3),(22,19),(33,34)]:
    rgb=rng.integers(0,256,(h,w,3),dtype=np.uint8);reference=integer_numpy(rgb,layers)
    raw=torch.tensor(rgb.transpose(2,0,1)[None].astype(np.float32),device='cuda')
    with torch.no_grad():gpu=array(integer_torch(raw,prepare_gpu(layers)));qat=array(model(raw/255,slot)*255)
    assert np.array_equal(reference,gpu) and np.array_equal(reference,qat),(slot,h,w);small+=1
  original_conv=torch.nn.functional.conv2d
  def traced(*args,**kwargs):
   out=original_conv(*args,**kwargs);shapes.append(list(out.shape));return out
  torch.nn.functional.conv2d=traced
  try:
   with torch.no_grad():model(torch.zeros(1,3,720,1280,device='cuda'),0)
  finally:torch.nn.functional.conv2d=original_conv
  assert len(shapes)==10 and all(v[-2:]==[720,1280] for v in shapes)
  assert maximum<2**21 and clipped==0
 result=dict(result='PREVIEW' if a.quick else 'PASS',catalog=CATALOG,cases=records,checkpoint_sha256=sha(a.checkpoint),step=meta['step'],refinement_steps=meta.get('refinement_steps'),training_visits=meta.get('training_visits'),small_cases=small,max_accumulator_bound=maximum,clipped_weights=clipped,spatial_shapes=shapes,full_resolution=not a.quick,board_images=False,
  sources_sha256={str(path):sha(path) for path in source_paths},reference_hashes=meta.get('reference_hashes',{}),outputs_sha256={str(path):sha(path) for path in folder.glob('*.png')},
  scope='Actual model predictions. Affine residual/gradient energy describe nontrivial spatial changes, not artistic-quality scores. Old four styles absent for six slots. No hardware export/bit update or board measurement.')
 (folder/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('EVALUATION',result['result'],'cases',len(records),'small',small,'bound',maximum,flush=True)
if __name__=='__main__':main()
