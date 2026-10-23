"""Compare baseline/refined/student on held-out data and integer agreement."""
from pathlib import Path
import argparse,json,time
import numpy as np
import torch
from PIL import Image,ImageOps,ImageDraw
from torchvision.transforms.functional import to_tensor
from prepare_styles import ROOT,STYLES
from style_network import load_network
from hardware_network import rgb565_roundtrip
from train_style import VGGFeatures,gram
from export_hardware import load_export,integer_network
from compare_styles import font,to_image


@torch.inference_mode()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,default=ROOT/'runs/four_styles_v1')
    parser.add_argument('--teacher',type=Path,default=ROOT/'runs/optimized_teacher_v2')
    parser.add_argument('--student',type=Path,default=ROOT/'runs/fpga_student_v2')
    parser.add_argument('--output',type=Path,default=ROOT/'results/optimized_v2')
    parser.add_argument('--styles',nargs='+',choices=STYLES,default=list(STYLES))
    parser.add_argument('--limit',type=int,default=48)
    parser.add_argument('--size',type=int,default=256)
    parser.add_argument('--teacher-only',action='store_true')
    args=parser.parse_args()
    torch.set_num_threads(4);torch.backends.cudnn.allow_tf32=False
    device='cuda' if torch.cuda.is_available() else 'cpu'
    split=json.loads((args.baseline/'split.json').read_text(encoding='utf-8'))
    # First 24 validation images select checkpoints; use the remaining 48 for
    # final comparison. No model training crop uses these filenames.
    names=split['validation'][24:24+args.limit]
    images=[]
    for name in names:
        with Image.open(ROOT/'convertpic/val2017'/name) as im:
            images.append(ImageOps.fit(ImageOps.exif_transpose(im).convert('RGB'),(args.size,args.size),Image.Resampling.LANCZOS))
    vgg=VGGFeatures(Path.home()/'.cache/torch/hub/checkpoints/vgg19-dcbb9e9d.pth').to(device).eval()
    args.output.mkdir(parents=True,exist_ok=True)
    report={'evaluation_names':names,'selection_count':24,'held_out_regression_count':len(names),
            'evaluation_scope':'not used for gradient training/checkpoint selection; reviewed during algorithm development, not a blind final benchmark',
            'styles':{}}
    for name in args.styles:
        reference=Image.open(ROOT/'styles'/f'{name}.jpg').convert('RGB')
        reference.thumbnail((512,512),Image.Resampling.LANCZOS)
        target=[gram(f) for f in vgg(to_tensor(reference).unsqueeze(0).to(device))]
        variants={'baseline':args.baseline/name/'model.pt','refined':args.teacher/name/'model.pt'}
        if not args.teacher_only:variants['student_qat']=args.student/name/'model.pt'
        results={};pictures={}
        for variant,checkpoint in variants.items():
            model,meta=load_network(checkpoint,device)
            totals=np.zeros(4);predictions=[]
            for start in range(0,len(images),6):
                x=torch.stack([to_tensor(i) for i in images[start:start+6]]).to(device)
                if variant=='student_qat':x=rgb565_roundtrip(x)
                y=model(x)
                if variant=='student_qat':y=rgb565_roundtrip(y)
                f=vgg(y)
                content=F_mse(f[2],vgg(x)[2])
                style=sum(F_mse(gram(a),b.expand(len(x),-1,-1)) for a,b in zip(f,target))
                tv=(y[...,1:,:]-y[...,:-1,:]).abs().mean()+(y[...,:,1:]-y[...,:,:-1]).abs().mean()
                clipped=((y<=0.001)|(y>=0.999)).float().mean()
                totals+=len(x)*np.array([content.item(),style.item(),tv.item(),clipped.item()])
                predictions.extend(to_image(i) for i in y)
            c,s,t,clip=(totals/len(images)).tolist()
            results[variant]={'content_mse':c,'style_gram_mse':s,'tv':t,'clipped_fraction':clip,
                              'epoch':meta.get('epoch',meta.get('completed_epochs')),'parameters':meta['parameters'],
                              'pixel_scope':'RGB565 input/output' if variant=='student_qat' else 'RGB888 teacher'}
            pictures[variant]=predictions
            del model
        if not args.teacher_only:
            manifest,layers=load_export(args.student/'export'/name)
            model,_=load_network(args.student/name/'model.pt','cpu')
            maximum=0;different=0;units=0
            for image in images[:6]:
                x=rgb565_roundtrip(to_tensor(image).unsqueeze(0))
                rgb=np.floor(x[0].permute(1,2,0).numpy()*255+.5).astype(np.uint8)
                integer=integer_network(rgb,layers,manifest['monochrome'])
                predicted=np.floor(model(x)[0].permute(1,2,0).numpy()*255+.5).clip(0,255).astype(np.uint8)
                diff=np.abs(integer.astype(np.int16)-predicted.astype(np.int16))
                maximum=max(maximum,int(diff.max()));different+=int(np.count_nonzero(diff));units+=diff.size
            results['integer_agreement']={'max_uint8_error':maximum,'different_channel_values':different,'compared_channel_values':units}
            if maximum:raise AssertionError(f'QAT/integer mismatch: {name}/{maximum}')
        for offset in range(0,len(images),6):
            cell=196;left=118;rows=1+len(variants);gap=6;top=52
            canvas=Image.new('RGB',(left+6*(cell+gap)+8,top+rows*(cell+28)),'white');draw=ImageDraw.Draw(canvas)
            draw.text((left,12),f'{STYLES[name]["label"]} · 原版 / 优化教师 / FPGA 定点网络',font=font(22),fill='black')
            for row,(label,items) in enumerate([('原图',images)]+[(k,pictures[k]) for k in variants]):
                y=top+row*(cell+28);draw.text((8,y+85),label,font=font(17),fill='#333')
                for col,image in enumerate(items[offset:offset+6]):
                    canvas.paste(image.resize((cell,cell),Image.Resampling.LANCZOS),(left+col*(cell+gap),y))
            canvas.save(args.output/f'{name}_{offset//6+1:02d}.jpg',quality=95)
        report['styles'][name]=results
        print(name,json.dumps(results),flush=True)
    (args.output/'evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


F_mse=torch.nn.functional.mse_loss
if __name__=='__main__':main()
