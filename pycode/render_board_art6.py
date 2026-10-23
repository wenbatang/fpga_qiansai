"""Render actual 720p RGB565 predictions and check full-size int64 reference."""
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np
import torch
from PIL import Image,ImageDraw
from art6_catalog import ROOT,RUN,STYLES,sha
from export_hardware import integer_network,load_export
from style_network import load_network
from compare_styles import font

@torch.inference_mode()
def main():
 p=argparse.ArgumentParser();p.add_argument('--image',type=Path,default=ROOT.parent/'xilinx/projects/uart_hdmi/images/0001.png');p.add_argument('--run',type=Path,default=RUN);a=p.parse_args()
 sys.path.insert(0,str(ROOT.parent/'xilinx/projects/uart_style_six/pc'))
 from send_image import load_rgb565
 torch.set_num_threads(4)
 payload=load_rgb565(a.image,False,1280,720)
 raw=np.frombuffer(payload,dtype='<u2').reshape(720,1280)
 r=(raw>>11)&31;g=(raw>>5)&63;b=raw&31
 rgb=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),-1).astype(np.uint8)
 x=torch.from_numpy(rgb.copy()).permute(2,0,1).float()[None]/255
 out=ROOT/'results'/a.run.name/'board_preview';out.mkdir(parents=True,exist_ok=True)
 Image.fromarray(rgb).save(out/'original_720p.png')
 result={'scope':'full 1280x720 software integer consistency and RGB565 preview; not board acceptance',
  'input_image':str(a.image.resolve()),'input_image_sha256':sha(a.image),'payload_sha256':hashlib.sha256(payload).hexdigest(),
  'size':[1280,720],'models':{},'hardware_programmed':False}
 canvas=Image.new('RGB',(1944,870),'#f6f4ef');draw=ImageDraw.Draw(canvas)
 draw.text((12,8),'六风格实际定点模型 · 1280×720原图输入',font=font(28),fill='#18304a')
 for index,name in enumerate(STYLES):
  model,meta=load_network(a.run/'student'/name/'model.pt','cpu')
  em,layers=load_export(a.run/'export'/name);assert em['checkpoint_sha256']==sha(a.run/'student'/name/'model.pt')
  actual=torch.floor(model(x)[0].permute(1,2,0)*255+.5).numpy().astype(np.uint8)
  expected=integer_network(rgb,layers,em['monochrome'])
  error=int(np.abs(actual.astype(np.int32)-expected.astype(np.int32)).max());assert error==0,(name,error)
  packed=((actual[...,0].astype(np.uint16)>>3)<<11)|((actual[...,1].astype(np.uint16)>>2)<<5)|(actual[...,2].astype(np.uint16)>>3)
  r=(packed>>11)&31;g=(packed>>5)&63;b=packed&31
  shown=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),-1).astype(np.uint8)
  im=Image.fromarray(shown);im.save(out/(name+'_720p.png'))
  col=index%3;row=index//3;left=12+col*644;top=56+row*393
  draw.text((left,top),f'{index} · '+STYLES[name]['label'],font=font(23),fill='#18304a')
  canvas.paste(im.resize((636,358),Image.Resampling.LANCZOS),(left,top+32))
  result['models'][name]={'checkpoint_sha256':em['checkpoint_sha256'],'integer_max_abs_error':error,
   'rgb_values_checked':actual.size,'prediction_sha256':sha(out/(name+'_720p.png'))}
  print('PASS full720 software integer',name,actual.size,flush=True)
 draw.text((12,canvas.height-25),'输入为用户0001.png；输出RGB565，与本轮模型对应。软件预测，非上板实测。',font=font(17),fill='#555555')
 canvas.save(out/'six_720p_comparison.png')
 (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
