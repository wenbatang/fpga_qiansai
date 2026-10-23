"""Verify and render the inference boundary fix without changing trained files."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
import torch
from PIL import Image,ImageDraw
from art6_catalog import ROOT,STYLES,sha
from art6_border import RUN,RESULTS,POLICY,load_export,integer_network,predict
from style_network import load_network
from hardware_network import rgb565_roundtrip
from compare_styles import font


def rgb565(rgb):
    r=rgb[...,0]>>3;g=rgb[...,1]>>2;b=rgb[...,2]>>3
    return np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),-1)


@torch.inference_mode()
def main():
    torch.set_num_threads(4)
    sys.path.insert(0,str(ROOT.parent/'xilinx/projects/uart_style_six/pc'))
    from send_image import load_rgb565
    source=ROOT.parent/'xilinx/projects/uart_style_six/images/0001.png'
    payload=load_rgb565(source,False,1280,720)
    raw=np.frombuffer(payload,dtype='<u2').reshape(720,1280)
    r=(raw>>11)&31;g=(raw>>5)&63;b=raw&31
    rgb=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),-1).astype('uint8')
    x=torch.from_numpy(rgb.copy()).permute(2,0,1).float()[None]/255
    out=RESULTS/'board_preview';out.mkdir(parents=True,exist_ok=True)
    Image.fromarray(rgb).save(out/'original_720p.png')
    receipt={'scope':'full720 software, unchanged weights, mirror inference boundaries; not board measurement',
        'padding':POLICY,'input_image':str(source),'input_image_sha256':sha(source),
        'payload_sha256':hashlib.sha256(payload).hexdigest(),'size':[1280,720],'models':{},
        'source_sha256':{str(p):sha(p) for p in [Path(__file__),ROOT/'art6_border.py']},'hardware_programmed':False}
    old_receipt=json.loads((ROOT/'results/art6_v2/board_preview/verification.json').read_text(encoding='utf-8'))
    assert receipt['payload_sha256']==old_receipt['payload_sha256']
    canvas=Image.new('RGB',(1944,870),'#f6f4ef');draw=ImageDraw.Draw(canvas)
    draw.text((12,8),'六风格 · 镜像边界修复 · 完整1280×720输入',font=font(28),fill='#18304a')
    for i,name in enumerate(STYLES):
        path=RUN/'student'/name/'model.pt';model,_=load_network(path)
        metadata,layers=load_export(RUN/'export'/name)
        actual=torch.floor(predict(model,x)[0].permute(1,2,0)*255+.5).numpy().astype('uint8')
        expected=integer_network(rgb,layers,metadata['monochrome'])
        error=int(np.abs(actual.astype('int32')-expected.astype('int32')).max());assert error==0
        shown=rgb565(actual)
        old=np.asarray(Image.open(ROOT/'results/art6_v2/board_preview'/(name+'_720p.png')))
        assert np.array_equal(old[31:-31,31:-31],shown[31:-31,31:-31]),name
        flat=[]
        for color in [(0,0,0),(128,128,128),(255,255,255),(255,64,0)]:
            constant=torch.tensor(color,dtype=torch.float32).view(1,3,1,1).expand(1,3,73,79)/255
            predicted=torch.floor(predict(model,rgb565_roundtrip(constant))*255+.5).to(torch.int32)
            flat.append(int((predicted-predicted[:,:,:1,:1]).abs().max()))
        assert max(flat)==0,(name,flat)
        Image.fromarray(shown).save(out/(name+'_720p.png'))
        left=12+i%3*644;top=56+i//3*393
        draw.text((left,top),str(i)+' · '+STYLES[name]['label'],font=font(23),fill='#18304a')
        canvas.paste(Image.fromarray(shown).resize((636,358),Image.Resampling.LANCZOS),(left,top+32))
        receipt['models'][name]={'checkpoint_sha256':sha(path),'integer_max_abs_error':error,
            'rgb_values_checked':actual.size,'interior_31px_unchanged':True,
            'uniform_input_nonuniformity':flat,'prediction_sha256':sha(out/(name+'_720p.png'))}
        print('PASS mirror full720',name,actual.size,'interior unchanged; uniform frame has no border',flush=True)
    draw.text((12,canvas.height-25),'原图未裁剪、未缩小。仅修改卷积边界；旧参数与旧结果保留。软件预测，非实板照片。',font=font(17),fill='#555555')
    canvas.save(out/'six_720p_comparison.png')
    pair=Image.new('RGB',(1280,402),'#f6f4ef');d=ImageDraw.Draw(pair)
    for col,(folder,label) in enumerate([(ROOT/'results/art6_v2/board_preview','修复前：补零产生色框'),(out,'修复后：镜像延伸，无裁剪')]):
        d.text((col*640+8,5),label,font=font(24),fill='#18304a')
        pair.paste(Image.open(folder/'ukiyoe_720p.png').resize((640,360),Image.Resampling.LANCZOS),(col*640,38))
    pair.save(out/'ukiyoe_before_after.png')
    (out/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
