"""Development regression for color diversity and integer agreement, not blind quality."""
from pathlib import Path
import argparse,hashlib,json,itertools
import numpy as np
import torch
from PIL import Image,ImageOps
from torchvision.transforms.functional import to_tensor
from prepare_styles import ROOT
from prepare_distinct_styles import STYLES
from style_network import load_network
from hardware_network import rgb565_roundtrip
from train_style import VGGFeatures,gram
from train_optimized import palette_quantiles
from export_hardware import load_export,integer_network

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,default=ROOT/'runs/distinct_student_v1')
    p.add_argument('--teacher',type=Path,default=ROOT/'runs/distinct_teacher_v2')
    p.add_argument('--output',type=Path,default=ROOT/'results/distinct_evaluation')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(4);torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
    device='cuda' if torch.cuda.is_available() else 'cpu'
    split=json.loads((a.run/'split.json').read_text());names=split['validation'][24:72]
    images=[]
    for name in names:
        with Image.open(ROOT/'convertpic/val2017'/name) as im:
            images.append(to_tensor(ImageOps.fit(ImageOps.exif_transpose(im).convert('RGB'),(256,256),Image.Resampling.LANCZOS)))
    vgg=VGGFeatures(Path.home()/'.cache/torch/hub/checkpoints/vgg19-dcbb9e9d.pth').to(device).eval()
    result={'scope':'48 development regression images, distinct from 24 selection images; not a blind final test',
            'names':names,'style_order':list(STYLES),'styles':{},'pairwise_output_l1':{}}
    outputs={}
    with torch.inference_mode():
        for name in STYLES:
            model,meta=load_network(a.run/name/'model.pt',device);teacher,_=load_network(a.teacher/name/'model.pt',device)
            ref=Image.open(ROOT/'styles/distinct_v1'/f'{name}.jpg').convert('RGB');ref.thumbnail((512,512))
            ref=to_tensor(ref).unsqueeze(0).to(device);targets=[gram(f) for f in vgg(ref)];palette=palette_quantiles(ref)
            stats=[];saved=[]
            for offset in range(0,len(images),6):
                x=rgb565_roundtrip(torch.stack(images[offset:offset+6]).to(device));raw=model(x);y=rgb565_roundtrip(raw)
                orig=vgg(x)[2];features=vgg(y);t=teacher(x)
                stats.append([float(torch.nn.functional.mse_loss(features[2],orig)),
                    float(sum(torch.nn.functional.mse_loss(gram(f),g.expand(len(y),-1,-1)) for f,g in zip(features,targets))),
                    float(torch.nn.functional.mse_loss(palette_quantiles(y),palette.expand(len(y),-1,-1))),
                    float((y.max(1).values-y.min(1).values).mean()),
                    float(((raw<=0)|(raw>=1)).float().mean()),float((y-t).abs().mean())])
                saved.append(y.cpu())
            outputs[name]=torch.cat(saved)
            exports,layers=load_export(a.run/'export'/name)
            exact_values=0;maximum=0
            cpu,_=load_network(a.run/name/'model.pt','cpu')
            for x in images[:6]:
                x=rgb565_roundtrip(x[None]);rgb=torch.floor(x[0].permute(1,2,0)*255+.5).numpy().astype(np.uint8)
                expected=integer_network(rgb,layers,exports['monochrome'])
                actual=torch.floor(cpu(x)[0].permute(1,2,0)*255+.5).numpy().astype(np.uint8)
                maximum=max(maximum,int(np.abs(actual.astype(np.int32)-expected.astype(np.int32)).max()))
                exact_values+=actual.size
            if maximum:raise AssertionError(f'Integer mismatch {name}: {maximum}')
            result['styles'][name]={'checkpoint_sha256':hashlib.sha256((a.run/name/'model.pt').read_bytes()).hexdigest(),
                'best_epoch':meta['epoch'],'steps':meta['step'],
                **dict(zip(('content','gram','palette','mean_chroma','clipped_fraction','teacher_l1'),np.mean(stats,0).tolist())),
                'integer_checked_values':exact_values,'integer_max_abs_error':maximum}
            print('EVALUATED',name,result['styles'][name],flush=True)
            del model,teacher,cpu
        for left,right in itertools.combinations(STYLES,2):
            result['pairwise_output_l1'][left+' / '+right]=float((outputs[left]-outputs[right]).abs().mean())
    (a.output/'evaluation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS distinct regression and integer reference',flush=True)

if __name__=='__main__':main()
