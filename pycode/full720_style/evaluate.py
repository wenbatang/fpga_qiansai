"""True720p held-out comparison, spatial-shape proof and independent integer checks."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
import torch
from PIL import Image,ImageOps,ImageDraw,ImageFont
from network import load,Layer
from integer import integer_numpy,integer_torch,prepare_gpu
ROOT=Path(__file__).resolve().parent;WS=ROOT.parents[1]
PROJECT=WS/'elinx/projects/camera_full720_30'
sys.path.insert(0,str(PROJECT/'scripts'))
from simutil import layers


def main():
    torch.set_num_threads(4);torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
    folder=PROJECT/'build/quality';folder.mkdir(parents=True,exist_ok=True)
    files=sorted((WS/'style_model/images').glob('*.png'));assert len(files)>=5
    model,meta=load(ROOT/'runs/c6_v1/model.pt','cuda');records=[]
    # Independent int64 vs exact float32 integer arithmetic, odd and tiny axes.
    rng=np.random.default_rng(71)
    for slot in range(4):
        for h,w in [(1,1),(5,3),(22,19),(33,34)]:
            x=rng.integers(0,256,(h,w,3),dtype=np.uint8)
            expected=integer_numpy(x,layers(slot));gpu=integer_torch(torch.tensor(x.transpose(2,0,1)[None].astype(np.float32),device='cuda'),prepare_gpu(layers(slot)))[0].permute(1,2,0).cpu().numpy().astype(np.uint8)
            assert np.array_equal(expected,gpu),(slot,h,w)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20)
    allshapes=[]
    for index in [0,4]:
        with Image.open(files[index]) as image:source=np.asarray(ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'),(1280,720),Image.Resampling.LANCZOS))
        r,g,b=source[:,:,0]>>3,source[:,:,1]>>2,source[:,:,2]>>3
        source=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),-1)
        x=torch.tensor(source.transpose(2,0,1)[None].astype(np.float32),device='cuda')
        canvas=Image.new('RGB',(1192,1090),'#f4f3ef');draw=ImageDraw.Draw(canvas)
        draw.text((10,8),'真实720p：原图 / 已签核C8半尺寸分支 / 新C6全尺寸分支',font=font,fill='#1c2e48')
        for slot,name in enumerate(['梵高','剪纸','漫画','水墨']):
            actual=integer_torch(x,prepare_gpu(layers(slot)))[0].permute(1,2,0).cpu().numpy().astype(np.uint8)
            expected=integer_numpy(source,layers(slot));assert np.array_equal(actual,expected)
            # Oracle teacher retained read-only; use the same definition as training.
            from train import Teacher
            if slot==0:teacher=Teacher()
            old=(teacher(x/255,torch.tensor([slot],device='cuda'))[0].permute(1,2,0).cpu().numpy()*255).round().astype(np.uint8)
            def to565(a):
                r,g,b=a[:,:,0]>>3,a[:,:,1]>>2,a[:,:,2]>>3
                return np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),-1)
            actual=to565(actual);old=to565(old)
            Image.fromarray(actual).save(folder/f'{files[index].stem}_{slot}_full720.png')
            for column,data in enumerate([source,old,actual]):canvas.paste(Image.fromarray(data).resize((384,216),Image.Resampling.LANCZOS),(10+column*396,48+slot*256))
            draw.text((10,268+slot*256),name,font=font,fill='#1c2e48')
            records.append(dict(source=files[index].name,slot=slot,pixels=921600,integer_max_abs_error=0,output_std=float(actual.std()),delta_vs_c8_mae=float(np.abs(actual.astype(float)-old).mean())))
        canvas.save(folder/f'{files[index].stem}_comparison.png')
        shape_trace=[]
        hooks=[module.register_forward_hook(lambda module,args,out:shape_trace.append(list(out.shape))) for module in model.modules() if isinstance(module,Layer)]
        with torch.no_grad():model(x/255,0)
        for hook in hooks:hook.remove()
        assert len(shape_trace)==9 and all(shape[-2:]==[720,1280] for shape in shape_trace)
        allshapes.append(shape_trace)
    weights=sum(l['w'].size for l in layers(0));assert weights==396
    inputs=[Path(__file__).resolve(),ROOT/'network.py',ROOT/'integer.py',ROOT/'train.py',ROOT/'runs/c6_v1/model.pt',PROJECT/'scripts/simutil.py',files[0],files[4]]
    inputs.extend((PROJECT/'parameters/c6').rglob('parameters.npz'))
    inputs.extend(WS/'style_model/parameters/c8'/f'{slot:02d}_{name}'/'parameters.npz' for slot,name in [(0,'vangogh'),(3,'papercut'),(4,'comic'),(5,'inkwash')])
    binding={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    outputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*.png')}
    (folder/'verification.json').write_text(json.dumps(dict(result='PASS',full_resolution=True,downsample=False,weights_per_style=weights,trainable_parameters=sum(p.numel() for p in model.parameters()),spatial_shapes=allshapes,cases=records,small_integer_cases=16,sources_sha256=binding,outputs_sha256=outputs,board_images=False),indent=2),encoding='utf-8')
    print('PASS 8 complete720p integer cases; all9 hidden layers720x1280; 396weights/style')


if __name__=='__main__':main()
