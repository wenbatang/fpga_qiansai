"""Same declared synthetic challenges on preserved and enhanced actual C."""
from pathlib import Path
import ctypes,json,os,sys
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(WS/'pycode/gesture_digits/calibrated_reference'))
from desktop_process import run
from simutil import sha
from check_calibrated import frame
def unpack(p):
 a=np.empty(4096,np.uint32);a[::2]=p&65535;a[1::2]=p>>16;return a.reshape(64,64)
def pack(p):
 a=np.asarray(p,np.uint32).ravel();return np.ascontiguousarray(a[::2]|(a[1::2]<<16))
def main():
 out=ROOT/'sim/gesture_stress';out.mkdir(exist_ok=True);os.environ['PATH']='E:/software/mingw/ucrt64/bin;'+os.environ['PATH']
 temp=out/'tmp';temp.mkdir(exist_ok=True);os.environ['TEMP']=os.environ['TMP']=str(temp)
 libs=[];sources=[ROOT.parent/'camera_art_ten_ui/firmware/gesture_calibrated.c',ROOT/'firmware/gesture_calibrated.c']
 for i,source in enumerate(sources):
  wrapper=out/f'wrapper{i}.c';wrapper.write_text('#include <stdint.h>\nstatic uint32_t pixels[2048];\n#define GESTURE_ROI_WORD(i) pixels[(i)]\n#include "'+source.as_posix()+'"\nvoid input_words(const uint32_t*p){for(unsigned i=0;i<2048;i++)pixels[i]=p[i];}\n',encoding='ascii')
  assert run(['E:/software/mingw/ucrt64/bin/gcc.exe','-shared','-O2',str(wrapper),'-o',str(out/f'classifier{i}.dll')],out,out/f'compile{i}.log')==0
  lib=ctypes.CDLL(str(out/f'classifier{i}.dll'));ptr=ctypes.POINTER(ctypes.c_uint32);lib.input_words.argtypes=[ptr]
  lib.cal_capture_template.argtypes=[ctypes.c_uint,ctypes.c_uint,ptr];lib.cal_predict.argtypes=[ptr];lib.cal_predict.restype=ctypes.c_int
  def feed(image):lib.input_words(image.ctypes.data_as(ptr))
  lib.cal_reset()
  for n in range(3):feed(frame());assert lib.cal_capture_background(n)==0
  for digit in range(10):
   for n,dx in enumerate([0,-2,2,1][:3+i]):
    feed(frame(digit,dx=dx));metrics=np.zeros(6,np.uint32);assert lib.cal_capture_template(digit,n,metrics.ctypes.data_as(ptr))==0
  libs.append(lib)
 cases=[]
 for digit in range(10):
  a=unpack(frame(digit));background=int(unpack(frame())[0,0])
  clutter=a.copy()
  for x,y in [(2,2),(54,3),(3,48)]:clutter[y:y+4,x:x+4]=0xbdf7
  hot=a.copy();hot[35,30]=0xffff
  variants=[('mirror',a[:,::-1]),('isolated_background_objects',clutter),('glare_pixel',hot)]
  for angle in [-5,5]:variants.append((f'rotation{angle}',np.asarray(Image.fromarray(a.astype(np.int32)).rotate(angle,resample=Image.Resampling.NEAREST,fillcolor=background))))
  for name,pixels in variants:
   image=pack(pixels);results=[]
   for lib in libs:
    lib.input_words(image.ctypes.data_as(ptr));m=np.zeros(6,np.uint32);results.append(int(lib.cal_predict(m.ctypes.data_as(ptr))))
   cases.append(dict(digit=digit,variant=name,baseline=results[0],enhanced=results[1]))
 totals=[]
 for key in ['baseline','enhanced']:
  totals.append(dict(correct=sum(c[key]==c['digit'] for c in cases),wrong=sum(c[key]>=0 and c[key]!=c['digit'] for c in cases),rejected=sum(c[key]<0 for c in cases)))
 assert totals[1]['correct']>totals[0]['correct'],totals
 assert totals[1]['wrong']<=totals[0]['wrong'],totals
 files=[Path(__file__),*sources,WS/'pycode/gesture_digits/calibrated_reference/check_calibrated.py',*out.glob('wrapper*.c')]
 result=dict(result='PASS',cases=cases,totals=dict(zip(['baseline','enhanced'],totals)),synthetic_cases=len(cases),
  sources_sha256={str(p):sha(p) for p in files},logs_sha256={str(p):sha(p) for p in out.glob('*.log')},
  scope='Actual old/new C, matched synthetic enrolled silhouettes; held-out mirror/clutter/glare/small rotation. Controlled robustness comparison, not real-camera or human accuracy.')
 (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(result['totals'])
if __name__=='__main__':main()
