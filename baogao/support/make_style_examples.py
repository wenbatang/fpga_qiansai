"""Twenty actual final-model integer predictions, never imagegen substitutes."""
from pathlib import Path
import hashlib,json,sys,time
import numpy as np,torch
from PIL import Image,ImageOps,ImageDraw,ImageFont
WS=Path(__file__).resolve().parents[2];ROOT=WS/'pycode/ten_style';REPORT=WS/'baogao'
if not (ROOT/'runs/ten_painterly_v2/model.pt').exists():ROOT=WS/'latest/pycode/ten_style'
sys.path.insert(0,str(ROOT))
from hardware_qat import load
from integer import model_layers,integer_torch,prepare_gpu,integer_numpy
from network import rgb565
from catalog import CATALOG
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 torch.set_num_threads(4);torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
 checkpoint=ROOT/'runs/ten_painterly_v2/model.pt';assert sha(checkpoint)=='7250b683772fdd9c3756f9f062ce639aadfcbfbc49eb64e6ac2e15588e489e86'
 out=REPORT/'assets/comparisons';out.mkdir(parents=True,exist_ok=True);model,meta=load(checkpoint,'cuda');cases=[];start=time.monotonic()
 font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',22)
 for name in ['mona_lisa','pearl_earring']:
  source=REPORT/'assets/source'/f'{name}.jpg';im=ImageOps.exif_transpose(Image.open(source)).convert('RGB');width=round(im.width*720/im.height);portrait=np.asarray(im.resize((width,720),Image.Resampling.LANCZOS));left=(1280-width)//2;right=1280-width-left;full=np.pad(portrait,((0,0),(left,right),(0,0)),mode='reflect').copy()
  raw=rgb565(torch.tensor(full.transpose(2,0,1)[None].astype(np.float32)/255,device='cuda'));pixel=(raw*255).round();original=pixel[0].permute(1,2,0).cpu().numpy().astype(np.uint8);Image.fromarray(original[:,left:left+width]).save(out/f'{name}_original.png')
  for slot in range(10):
   layers=model_layers(model,slot)
   with torch.no_grad():
    y=integer_torch(pixel,prepare_gpu(layers));q=model(raw,slot)*255
   actual=y[0].permute(1,2,0).round().clamp(0,255).cpu().numpy().astype(np.uint8);qat=q[0].permute(1,2,0).round().clamp(0,255).cpu().numpy().astype(np.uint8);assert np.array_equal(actual,qat),(name,slot)
   independent=None
   if slot==0:assert np.array_equal(integer_numpy(original,layers),actual);independent=0
   target=out/f'{name}_{slot:02d}.png';Image.fromarray(actual[:,left:left+width]).save(target)
   # Consistent panels, two content examples per style. White margins only in
   # layout; no change to model pixels, no sharpening or color postprocessing.
   cases.append(dict(content=name,slot=slot,label=CATALOG[slot]['label'],full_inference_size=[1280,720],displayed_crop=[left,0,width,720],padding='reflect101 around aspect-preserved portrait',qat_max_error=0,independent_int64_error=independent,output=str(target),sha256=sha(target),source_sha256=sha(source)))
   print('EXAMPLE',name,slot,'seconds',round(time.monotonic()-start),flush=True)
 for slot in range(10):
  canvas=Image.new('RGB',(1380,540),'white');d=ImageDraw.Draw(canvas)
  for col,name in enumerate(['mona_lisa','pearl_earring']):
   for j,path in enumerate([out/f'{name}_original.png',out/f'{name}_{slot:02d}.png']):
    image=ImageOps.contain(Image.open(path),(320,730),Image.Resampling.LANCZOS);x=col*690+j*335+(320-image.width)//2;canvas.paste(image,(x,48));d.text((col*690+j*335+10,8),'原图' if j==0 else CATALOG[slot]['label'],font=font,fill='#172c46')
  canvas.save(out/f'style_{slot:02d}_pairs.png')
 (out/'verification.json').write_text(json.dumps(dict(result='PASS',cases=cases,model_sha256=sha(checkpoint),source_sha256=sha(__file__),step=meta['step'],board_photographs=False,scope='Twenty actual complete720p integer outputs. Two independent int64 full-frame checks; all twenty QAT exact. Figure crops preserve portrait aspect. No artistic-quality score.'),ensure_ascii=False,indent=2),encoding='utf-8')
 print('PASS 20 actual examples',flush=True)
if __name__=='__main__':main()
