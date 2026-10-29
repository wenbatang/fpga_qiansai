"""Actual photo previews. Quick float candidates are never called FPGA output."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,sys
import numpy as np
from PIL import Image,ImageOps,ImageDraw,ImageFont
import torch
from network import load as float_load,rgb565,base
from hardware_qat import load as hardware_load
from integer import model_layers,integer_numpy,integer_torch,prepare_gpu
ROOT=Path(__file__).resolve().parent;PY=ROOT.parent;WS=PY.parent;PROJECT=WS/'elinx/projects/camera_art_interactive'
sys.path.append(str(PY));from style_network import load_network


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',type=Path,default=ROOT/'runs/paint_final/model.pt');parser.add_argument('--quick',action='store_true');a=parser.parse_args()
    torch.set_num_threads(4);torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
    metadata=torch.load(a.checkpoint,map_location='cpu',weights_only=True)
    model,meta=(hardware_load if metadata.get('hardware_qat') else float_load)(a.checkpoint,'cuda');old,oldmeta=base.load(PY/'full720_style/runs/c6_v1/model.pt','cuda')
    folder=PROJECT/'build'/('preview_training' if a.quick else 'quality');folder.mkdir(parents=True,exist_ok=True)
    size=(512,288) if a.quick else (1280,720);records=[];shapes=[];sources=[a.checkpoint,Path(__file__),ROOT/'network.py',ROOT/'hardware_qat.py',ROOT/'integer.py',ROOT/'train.py',PY/'full720_style/network.py']
    for filename in ['0001.png','0005.png']:
        path=WS/'style_model/images'/filename;sources.append(path)
        with Image.open(path) as image:array=np.asarray(ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'),size,Image.Resampling.LANCZOS)).copy()
        x=rgb565(torch.from_numpy(array.transpose(2,0,1)[None].astype(np.float32)/255).cuda())
        array=(x[0].permute(1,2,0).cpu().numpy()*255).round().astype(np.uint8)
        canvas=Image.new('RGB',(1354,930),'#f6f3ed');draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
        draw.text((12,8),f'实际模型输出 · 第{meta["step"]}步 · 原图 / 保留C6 / 新教师 / 新学生'+('（定点精修候选）' if a.quick and meta.get('hardware_qat') else '（训练中浮点候选）' if a.quick else '（整数720p）'),font=font,fill='#22334b')
        for slot,name in enumerate(['梵高','剪纸','漫画','水墨']):
            teacher_path=ROOT/'runs/paint_v1/teachers'/['vangogh','papercut','comic','inkwash'][slot]/'model.pt';sources.append(teacher_path);teacher,_=load_network(teacher_path,'cuda')
            with torch.no_grad():
                previous=old(x,slot);desired=teacher(x)
                if a.quick:actual=model(x,slot)
                else:actual=integer_torch((x*255).round(),prepare_gpu(model_layers(model,slot)))/255
            def to_array(value):return (value[0].permute(1,2,0).float().clamp(0,1).cpu().numpy()*255).round().astype(np.uint8)
            actual=to_array(actual);previous=to_array(previous);desired=to_array(desired)
            if not a.quick:
                expected=integer_numpy(array,model_layers(model,slot));assert np.array_equal(expected,actual),(filename,slot)
                with torch.no_grad():hardware_actual=to_array(model(x,slot))
                assert np.array_equal(expected,hardware_actual),(filename,slot,'hardware QAT forward differs')
                Image.fromarray(actual).save(folder/f'{path.stem}_{slot}_720p.png')
                mask=array.mean(2)>.8*255;records.append(dict(source=filename,slot=slot,pixels=921600,integer_max_abs_error=0,hardware_qat_max_abs_error=0,output_std=float(actual.std()),bright_output_mean=float(actual[mask].mean()) if mask.any() else None,bright_before_mean=float(previous[mask].mean()) if mask.any() else None,chroma_mean=float(np.abs(actual.astype(float)-actual.mean(2,keepdims=True)).mean())))
            for column,value in enumerate([array,previous,desired,actual]):canvas.paste(Image.fromarray(value).resize((324,182),Image.Resampling.LANCZOS),(12+column*336,44+slot*218))
            draw.text((12,228+slot*218),name,font=font,fill='#22334b');del teacher
        canvas.save(folder/f'{path.stem}_comparison.png')
        if not a.quick:
            # The folded-QAT path uses functional convolutions. Observe those
            # actual tensors here; restore the function even on failure.
            trace=[];original_conv=torch.nn.functional.conv2d
            def observed_conv(*args,**kwargs):
                result=original_conv(*args,**kwargs);trace.append(list(result.shape));return result
            torch.nn.functional.conv2d=observed_conv
            try:
                with torch.no_grad():model(x,0)
            finally:torch.nn.functional.conv2d=original_conv
            assert len(trace)==10;trace=trace[:-1]
            assert len(trace)==9 and all(z[-2:]==[720,1280] for z in trace);shapes.append(trace)
    if not a.quick:
        rng=np.random.default_rng(53)
        for slot in range(4):
            for h,w in [(1,1),(5,3),(22,19),(33,34)]:
                array=rng.integers(0,256,(h,w,3),dtype=np.uint8);expected=integer_numpy(array,model_layers(model,slot));x=torch.tensor(array.transpose(2,0,1)[None].astype(np.float32),device='cuda')
                value=integer_torch(x,prepare_gpu(model_layers(model,slot)))[0].permute(1,2,0).cpu().numpy().astype(np.uint8);assert np.array_equal(expected,value)
        sources.extend((PROJECT/'parameters/c6').rglob('parameters.npz'))
        assert meta.get('hardware_qat') and meta['step']>=14000
        assert not any(l['clipped_weights'] for slot in range(4) for l in model_layers(model,slot))
        receipt=dict(result='PASS',full_resolution=True,downsample=False,hardware_qat=True,weights_per_style=396,trainable_parameters=sum(p.numel() for p in model.parameters()),independent_styles=True,spatial_shapes=shapes,cases=records,small_integer_cases=16,board_images=False,sources_sha256={str(p):sha(p) for p in sources},outputs_sha256={str(p):sha(p) for p in folder.glob('*.png')})
        (folder/'verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('ACTUAL PREVIEW',meta['step'],folder,flush=True)


if __name__=='__main__':main()
