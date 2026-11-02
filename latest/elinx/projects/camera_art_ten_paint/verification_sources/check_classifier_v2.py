"""Actual optional calibration C vs independent reference on declared fixtures."""
from pathlib import Path
import ctypes,hashlib,json,os,sys,subprocess
import numpy as np
from PIL import Image,ImageDraw
from gesture_reference import Calibration
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/"pycode/gesture_digits/calibrated_reference"))
from check_calibrated import frame
ROOT=Path(__file__).resolve().parents[1];FIRMWARE=ROOT/'firmware'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 old_source=Path(__file__).resolve().parents[4]/'pycode/gesture_digits/calibrated_reference/check_calibrated.py'
 out=ROOT/'sim/classifier_v2';out.mkdir(parents=True,exist_ok=True);source=FIRMWARE/'gesture_calibrated.c';wrapper=out/'wrapper.c'
 wrapper.write_text('#include <stdint.h>\nstatic uint32_t fixture[2048];\n#define GESTURE_ROI_WORD(i) fixture[(i)]\n#include "'+source.as_posix()+'"\nvoid input_words(const uint32_t *p){for(unsigned i=0;i<2048;i++)fixture[i]=p[i];}\nvoid trace_features(uint8_t *p){for(unsigned i=0;i<192;i++)p[i]=cal_f[i];}\nvoid trace_canonical(uint8_t *p){for(unsigned i=0;i<4096;i++)p[i]=cal_canon[i];}\n',encoding='ascii')
 os.environ['PATH']='E:/software/mingw/ucrt64/bin;'+os.environ['PATH'];temp=ROOT/'build/tmp';temp.mkdir(exist_ok=True);os.environ['TEMP']=os.environ['TMP']=str(temp)
 sys.path.insert(0,str(FIRMWARE.parent/'scripts'));from desktop_process import run
 assert run(['E:/software/mingw/ucrt64/bin/gcc.exe','-shared','-O2',str(wrapper),'-o',str(out/'calibrated.dll')],out,out/'compile.log')==0
 lib=ctypes.CDLL(str(out/'calibrated.dll'));p32=ctypes.POINTER(ctypes.c_uint32);p8=ctypes.POINTER(ctypes.c_uint8)
 lib.input_words.argtypes=[p32];lib.cal_predict.argtypes=[p32];lib.cal_predict.restype=ctypes.c_int;lib.cal_capture_template.argtypes=[ctypes.c_uint,ctypes.c_uint,p32];lib.cal_capture_template.restype=ctypes.c_int;lib.cal_capture_background.argtypes=[ctypes.c_uint];lib.cal_capture_background.restype=ctypes.c_int
 ref=Calibration();records=[];feature_values=0;canonical_values=0
 def call(operation,words,*args):
  nonlocal feature_values,canonical_values
  lib.input_words(words.ctypes.data_as(p32));m=np.zeros(6,np.uint32)
  if operation=='background':got=lib.cal_capture_background(*args);want=ref.capture_background(*args,words);md=None
  elif operation=='template':got=lib.cal_capture_template(*args,m.ctypes.data_as(p32));want,md=ref.capture_template(*args,words)
  else:got=lib.cal_predict(m.ctypes.data_as(p32));want,md=ref.predict(words)
  assert got==want,(operation,args,got,want)
  if md is not None:
   assert list(map(int,m))==list(md.values()),(operation,args,list(m),md)
   if md['reason'] not in [1,2,3,5]:
    f=np.zeros(192,np.uint8);c=np.zeros(4096,np.uint8);lib.trace_features(f.ctypes.data_as(p8));lib.trace_canonical(c.ctypes.data_as(p8));assert np.array_equal(f,ref.features);assert np.array_equal(c,ref.canonical.ravel());feature_values+=192;canonical_values+=4096
  assert lib.cal_valid_mask()==ref.valid_mask()
  records.append(dict(operation=operation,args=args,result=got,metrics=md));return got
 lib.cal_reset();assert call('predict',frame(1))==-2
 assert call('background',frame(),1)==-2
 for n in range(3):assert call('background',frame(),n)==0
 assert call('template',frame(),0,0)==-1
 assert call('template',frame(1),0,1)==-2
 assert call('predict',frame(1))==-2
 for digit in range(10):
  for n,dx in enumerate([0,-2,2,1]):assert call('template',frame(digit,dx=dx),digit,n)==0
 assert lib.cal_valid_mask()==1023
 predictions=[]
 for digit in range(10):
  for variant,kw in [('same',{}),('shift',dict(dx=-3,dy=-2)),('small',dict(scale=.85)),('green_dark',dict(hand=(25,51,34))),('brighter_bg',dict(bright=12))]:
   got=call('predict',frame(digit,**kw));predictions.append(dict(digit=digit,variant=variant,result=got));
   if variant in ['same','shift','small','green_dark','brighter_bg']:assert got==digit,(digit,variant,got,records[-1])
 assert call('predict',frame())==-1
 assert call('predict',frame(bright=12))==-1
 # An already-valid class can be replaced; partial recapture is never valid.
 lib.cal_restart_class(3);ref.restart_class(3);assert lib.cal_valid_mask()==(1023^(1<<3));assert call('predict',frame(3))==-2
 for n in range(4):assert call('template',frame(3),3,n)==0
 assert lib.cal_valid_mask()==1023 and call('predict',frame(3))==3
 lib.cal_restart_class(10);ref.restart_class(10);assert lib.cal_valid_mask()==1023
 # Duplicate class templates must be ambiguous even on their exact image.
 lib.cal_reset();ref.reset()
 for n in range(3):call('background',frame(),n)
 for digit in range(10):
  for n in range(4):call('template',frame(0),digit,n)
 assert call('predict',frame(0))==-2 and records[-1]['metrics']['reason']==7
 # Recapturing background0 invalidates every old prototype.
 assert call('background',frame(),0)==0 and lib.cal_valid_mask()==0
 # Noisy/variable background estimation and adaptive-threshold limits.
 for n,level in enumerate([12,18,10]):assert call('background',frame(background=(level,level,level)),n)==0
 assert ref.threshold==6
 for n,level in enumerate([8,180,20]):assert call('background',frame(background=(level,level,level)),n)==0
 assert ref.threshold==6
 # Production object has no host fixture; report actual target text/BSS.
 tool=Path('E:/softare_FPGA/xpack-riscv-none-elf-gcc-15.2.0-1-win32-x64/xpack-riscv-none-elf-gcc-15.2.0-1/bin')
 assert run([str(tool/'riscv-none-elf-gcc.exe'),'-march=rv32im_zicsr','-mabi=ilp32','-Os','-ffreestanding','-fno-builtin','-c',str(source),'-o','calibrated.o'],out,out/'rv32_compile.log')==0
 assert run([str(tool/'riscv-none-elf-size.exe'),'calibrated.o'],out,out/'rv32_size.log')==0
 size=(out/'rv32_size.log').read_text();numbers=list(map(int,size.splitlines()[-1].split()[:3]));assert numbers[2]<20000,numbers
 files=[source,Path(__file__),Path(__file__).with_name('gesture_reference.py'),old_source,wrapper]
 result=dict(result='PASS',calls=records,predictions=predictions,feature_values_equal=feature_values,canonical_values_equal=canonical_values,target_text_bytes=numbers[0],target_data_bytes=numbers[1],target_bss_bytes=numbers[2],sources_sha256={str(p):sha(p) for p in files},scope='Optional supervised prototype candidate, synthetic silhouettes/colors and exact C/Python integer equivalence; not real SC431HAI accuracy, full linked RAM usage or board acceptance')
 (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in result.items() if k not in ['calls','predictions','sources_sha256']},indent=2),flush=True)
if __name__=='__main__':main()
