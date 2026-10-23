"""Use the user's real 720p input and save bit-exact four-style integer previews."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import torch
from PIL import Image,ImageDraw,ImageOps
from torchvision.transforms.functional import to_tensor
from prepare_styles import ROOT
from prepare_distinct_styles import STYLES
from style_network import load_network
from hardware_network import rgb565_roundtrip
from export_hardware import load_export,integer_network
from compare_styles import font,to_image

def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=Path)
    p.add_argument('--run',type=Path,default=ROOT/'runs/distinct_student_v1')
    p.add_argument('--output',type=Path,default=ROOT/'results/distinct_real_720p')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);torch.set_num_threads(4)
    source=ImageOps.exif_transpose(Image.open(a.input)).convert('RGB');source.save(a.output/'input.png')
    x=rgb565_roundtrip(to_tensor(source)[None]);rgb=torch.floor(x[0].permute(1,2,0)*255+.5).numpy().astype(np.uint8)
    images=[('原图',source)];report={'input':str(a.input.resolve()),'size':source.size,'input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),
        'scope':'CPU QAT vs independent int64 reference, complete real image; not HDMI readback','styles':{}}
    with torch.inference_mode():
        for name,spec in STYLES.items():
            meta,layers=load_export(a.run/'export'/name);intermediates=[]
            expected=integer_network(rgb,layers,meta['monochrome'],intermediates)
            model,_=load_network(a.run/name/'model.pt');raw=model(x)
            actual=torch.floor(raw[0].permute(1,2,0)*255+.5).numpy().astype(np.uint8)
            if not np.array_equal(actual,expected):raise AssertionError('Integer disagreement: '+name)
            np.savez_compressed(a.output/f'{name}_layers.npz',input_rgb=rgb,**{f'layer{i}':v for i,v in enumerate(intermediates)})
            output=to_image(rgb565_roundtrip(raw)[0]);output.save(a.output/f'{name}.png');images.append((spec['label'],output))
            report['styles'][name]={'checked_values':actual.size,'max_abs_error':0,'checkpoint_sha256':meta['checkpoint_sha256']}
            print('REAL IMAGE PASS',name,actual.size,'channel values',flush=True)
            del model,intermediates
    cell_w,cell_h=560,315;pad=18;row_h=cell_h+55
    canvas=Image.new('RGB',(3*cell_w+4*pad,2*row_h+pad),'#edf2f7');draw=ImageDraw.Draw(canvas)
    for i,(label,im) in enumerate(images):
        col,row=i%3,i//3;left=pad+col*(cell_w+pad);top=pad+row*row_h
        draw.text((left,top),label,font=font(25),fill='#193453');canvas.paste(ImageOps.contain(im,(cell_w,cell_h)),(left,top+40))
    draw.text((pad+2*(cell_w+pad),pad+row_h+75),'实际 720p 原图\n四种训练风格\nRGB565 定点参考\n逐层整数验证通过',font=font(25),fill='#193453',spacing=16)
    canvas.save(a.output/'comparison.jpg',quality=95)
    (a.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
