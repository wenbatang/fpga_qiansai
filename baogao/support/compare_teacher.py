"""Evaluate retained painting teachers and the deployed student on the same two 720p inputs."""
import json
from pathlib import Path
import sys
import cv2
import numpy as np
from PIL import Image
import torch

REPORT=Path(__file__).resolve().parents[1]
PYCODE=REPORT.parent/'latest/pycode'
sys.path[:0]=[str(PYCODE/'ten_style'),str(PYCODE)]
from style_network import load_network
from hardware_qat import load
from integer import model_layers,prepare_gpu,integer_torch

def score(a,b):
    a=a.astype(np.float64); b=b.astype(np.float64)
    def mean(image):
        return cv2.GaussianBlur(image,(11,11),1.5)
    ma,mb=mean(a),mean(b)
    c1,c2=(.01*255)**2,(.03*255)**2
    numerator=(2*ma*mb+c1)*(2*(mean(a*b)-ma*mb)+c2)
    denominator=(ma**2+mb**2+c1)*(mean(a*a)-ma**2+mean(b*b)-mb**2+c2)
    return float(10*np.log10(255**2/np.mean((a-b)**2))), float(np.mean((numerator/denominator)[5:-5,5:-5]))

def elapsed(fn):
    for _ in range(3):fn()
    torch.cuda.synchronize()
    samples=[]
    for _ in range(12):
        a=torch.cuda.Event(enable_timing=True);b=torch.cuda.Event(enable_timing=True)
        a.record();result=fn();b.record();b.synchronize();samples.append(a.elapsed_time(b))
    return result,float(np.median(samples))

@torch.inference_mode()
def main():
    torch.backends.cudnn.allow_tf32=False
    torch.backends.cuda.matmul.allow_tf32=False
    student,_=load(PYCODE/'ten_style/runs/ten_painterly_v2/model.pt','cuda')
    rows=[]
    for slot,name in [(0,'vangogh'),(2,'papercut'),(3,'comic'),(4,'inkwash')]:
        teacher,_=load_network(PYCODE/'painterly_style/runs/paint_v1/teachers'/name/'model.pt','cuda')
        weights=prepare_gpu(model_layers(student,slot))
        for image in ['mona_lisa','pearl_earring']:
            img=np.asarray(Image.open(REPORT/'assets/comparisons'/f'{image}_original.png').convert('RGB'))
            w=img.shape[1]; left=(1280-w)//2
            padded=np.pad(img,((0,0),(left,1280-w-left),(0,0)),mode='reflect')
            raw=torch.from_numpy(padded.copy()).permute(2,0,1)[None].float().cuda()
            norm=raw/255
            t,tms=elapsed(lambda:teacher(norm))
            s,sms=elapsed(lambda:integer_torch(raw,weights))
            target=(255*t).round().clamp(0,255)[0].permute(1,2,0).byte().cpu().numpy()[:,left:left+w]
            result=s[0].permute(1,2,0).byte().cpu().numpy()[:,left:left+w]
            assert np.array_equal(result,np.asarray(Image.open(REPORT/'assets/comparisons'/f'{image}_{slot:02d}.png')))
            psnr,ssim=score(target,result)
            rows.append(dict(slot=slot,content=image,psnr=psnr,ssim=ssim,teacher_ms=tms,student_reference_ms=sms,teacher_parameters=sum(p.numel() for p in teacher.parameters())))
    doc=dict(gpu=torch.cuda.get_device_name(),cases=rows,scope='Two portraits, batch=1 720p GPU compute. Three warmups and median of 12 CUDA event intervals per case. RGB SSIM (11x11 Gaussian sigma 1.5) and PSNR on portrait area only. Teacher output is the reference.')
    (REPORT/'assets/comparisons/teacher_benchmark.json').write_text(json.dumps(doc,indent=2),encoding='utf8')
    print(json.dumps(doc))
if __name__=='__main__':main()
