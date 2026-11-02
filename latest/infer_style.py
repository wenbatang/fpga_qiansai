"""Use the frozen final hardware-arithmetic model on a local content image."""
from pathlib import Path
import argparse,sys
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'pycode/ten_style'))
def main():
 import numpy as np,torch
 from PIL import Image,ImageOps
 from hardware_qat import load
 from integer import model_layers,integer_torch,prepare_gpu,integer_numpy
 from network import rgb565
 p=argparse.ArgumentParser();p.add_argument('image',type=Path);p.add_argument('--style',type=int,choices=range(10),default=0);p.add_argument('--out',type=Path,default=ROOT/'results/prediction.png');a=p.parse_args();torch.set_num_threads(4);torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False;device='cuda' if torch.cuda.is_available() else 'cpu';model,_=load(ROOT/'pycode/ten_style/runs/ten_painterly_v2/model.pt',device)
 image=ImageOps.exif_transpose(Image.open(a.image)).convert('RGB');image=ImageOps.fit(image,(1280,720),Image.Resampling.LANCZOS);raw=(rgb565(torch.tensor(np.array(image).transpose(2,0,1)[None]/255,dtype=torch.float32,device=device))*255).round();layers=model_layers(model,a.style)
 with torch.no_grad():
  if device=='cuda':result=integer_torch(raw,prepare_gpu(layers))[0].permute(1,2,0).cpu().numpy()
  else:result=integer_numpy(raw[0].permute(1,2,0).cpu().numpy().round().astype(np.uint8),layers)
 a.out.parent.mkdir(parents=True,exist_ok=True);Image.fromarray(result.round().clip(0,255).astype(np.uint8)).save(a.out);print(a.out)
if __name__=='__main__':main()
