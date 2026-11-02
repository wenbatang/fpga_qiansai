"""Real teacher/student photo comparison plus independent int64 verification."""
from pathlib import Path
import argparse,hashlib,json,math
import numpy as np
from PIL import Image,ImageOps,ImageDraw,ImageFont
import torch
from catalog import ROOT,WS,CATALOG
from network import load as float_load,rgb565,BASE
from hardware_qat import load as hardware_load
from integer import model_layers,integer_numpy,integer_torch,prepare_gpu
from train import teachers,sha
import teacher_integer
def tensor_array(value):return value[0].permute(1,2,0).float().clamp(0,255).round().cpu().numpy().astype(np.uint8)
def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,default=ROOT/'runs/ten_c6_v2/model.pt');p.add_argument('--quick',action='store_true');a=p.parse_args()
    torch.set_num_threads(4);torch.backends.cudnn.allow_tf32=False;torch.backends.cuda.matmul.allow_tf32=False
    data=torch.load(a.checkpoint,map_location='cpu',weights_only=True)
    model,meta=(hardware_load if data.get('hardware_qat') else float_load)(a.checkpoint,'cuda')
    folder=ROOT/'results'/('quick' if a.quick else 'final');folder.mkdir(parents=True,exist_ok=True)
    size=(512,288) if a.quick else (1280,720)
    desired_layers,teacher_hashes=teachers();all_layers=[model_layers(model,s) for s in range(10)]
    gpu_layers=[prepare_gpu(layers) for layers in all_layers];records=[];files=[a.checkpoint,Path(__file__),ROOT/'network.py',ROOT/'integer.py',ROOT/'hardware_qat.py',ROOT/'train.py',ROOT/'teacher_integer.py',ROOT/'catalog.py',BASE]
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
    for filename in ['0001.png','0005.png']:
        path=WS/'style_model/images'/filename;files.append(path)
        with Image.open(path) as image:array=np.asarray(ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'),size,Image.Resampling.LANCZOS)).copy()
        x=rgb565(torch.tensor(array.transpose(2,0,1)[None].astype(np.float32)/255,device='cuda'));raw=(x*255).round();array=tensor_array(raw)
        width,height=324,182;canvas=Image.new('RGB',(1040,10*230+64),'#f4f2ed');draw=ImageDraw.Draw(canvas)
        draw.text((12,8),f'真实软件输出 · {meta["step"]}步 · 原图 / 所选C8整数教师 / 新全720p C6'+('（快速候选）' if a.quick else '（最终整数）'),font=font,fill='#22334b')
        for item,layers,gpu in zip(CATALOG,all_layers,gpu_layers):
            slot=item['slot']
            with torch.no_grad():
                teacher=tensor_array(teacher_integer.integer_torch(raw,desired_layers[slot]))
                actual=tensor_array(model(x,slot)*255) if a.quick else tensor_array(integer_torch(raw,gpu))
            if not a.quick:
                expected=integer_numpy(array,layers);assert np.array_equal(actual,expected),(filename,slot,'NumPy')
                with torch.no_grad():qat=tensor_array(model(x,slot)*255)
                assert np.array_equal(qat,expected),(filename,slot,'folded hardware QAT')
                Image.fromarray(actual).save(folder/f'{path.stem}_{slot:02d}_{item["name"]}_720p.png')
                Image.fromarray(teacher).save(folder/f'{path.stem}_{slot:02d}_teacher_720p.png')
            diff=actual.astype(np.float32)-teacher.astype(np.float32);mse=float((diff*diff).mean())
            record=dict(source=filename,**item,pixels=int(np.prod(actual.shape[:2])),teacher_student_l1=float(np.abs(diff).mean()),teacher_student_psnr=99. if mse==0 else 10*math.log10(255*255/mse),integer_max_abs_error=None if a.quick else 0,hardware_qat_max_abs_error=None if a.quick else 0,output_rgb_mean=actual.mean((0,1)).tolist(),output_std=float(actual.std()))
            records.append(record)
            for col,value in enumerate([array,teacher,actual]):canvas.paste(Image.fromarray(value).resize((width,height),Image.Resampling.LANCZOS),(12+col*340,44+slot*230))
            draw.text((12,232+slot*230),f'手势{slot} / 源{item["source_id"]} {item["label"]}',font=font,fill='#22334b')
        canvas.save(folder/f'{path.stem}_comparison.png')
    small=0;shape_trace=[]
    if not a.quick:
        rng=np.random.default_rng(20261102)
        for slot,layers in enumerate(all_layers):
            for h,w in [(1,1),(5,3),(22,19),(33,34)]:
                array=rng.integers(0,256,(h,w,3),dtype=np.uint8);expected=integer_numpy(array,layers)
                x=torch.tensor(array.transpose(2,0,1)[None].astype(np.float32),device='cuda')
                with torch.no_grad():got=tensor_array(integer_torch(x,gpu_layers[slot]))
                assert np.array_equal(got,expected);small+=1
        original=torch.nn.functional.conv2d
        def traced(*args,**kwargs):
            y=original(*args,**kwargs);shape_trace.append(list(y.shape));return y
        torch.nn.functional.conv2d=traced
        try:
            with torch.no_grad():model(torch.zeros(1,3,720,1280,device='cuda'),0)
        finally:torch.nn.functional.conv2d=original
        assert len(shape_trace)==10 and all(shape[-2:]==[720,1280] for shape in shape_trace)
        assert data['hardware_qat'] and data['step']>=11000
        assert all(l['clipped_weights']==0 for layers in all_layers for l in layers)
    v=dict(result='PREVIEW' if a.quick else 'PASS',catalog=CATALOG,cases=records,small_integer_cases=small,spatial_shapes=shape_trace,teacher_downsample=True,student_downsample=False,full_resolution=not a.quick,source_hashes={str(path):sha(path) for path in files},teacher_hashes=teacher_hashes,outputs_sha256={str(path):sha(path) for path in folder.glob('*.png')},board_images=False,trainable_parameters=sum(p.numel() for p in model.parameters()),scope='Frozen C8 INT8 targets; real C6 software output, no AI conceptual images or board accuracy claim')
    (folder/'verification.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
    print('TEN STYLE EVALUATION',v['result'],'mean PSNR',sum(r['teacher_student_psnr'] for r in records)/len(records),'small',small,folder,flush=True)
if __name__=='__main__':main()
