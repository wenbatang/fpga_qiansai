from pathlib import Path
import ctypes,hashlib,json,sys,os
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from desktop_process import run


def pose(n,chinese=False):
    image=Image.new('1',(64,64));d=ImageDraw.Draw(image)
    d.rectangle((19,31,46,53),fill=1);d.rectangle((28,52,37,63),fill=1)
    for index in range(min(n,4) if not chinese else 2):
        x=20+index*7;top=[9,5,9,16][index]
        d.rounded_rectangle((x,top,x+4,35),radius=2,fill=1)
    if chinese or n==5:d.polygon([(21,44),(8,30),(10,25),(25,34),(29,41)],fill=1)
    return np.asarray(image,dtype=np.uint8)


def main():
    out=ROOT/'sim/classifier';out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'firmware/gesture_classify.c';library=out/'classifier.dll'
    os.environ['PATH']='E:/software/mingw/ucrt64/bin;'+os.environ['PATH']
    assert run(['E:/software/mingw/ucrt64/bin/gcc.exe','-shared','-O2','-Wall','-Wextra',str(source),'-o',str(library)],out,out/'compile.log')==0
    lib=ctypes.CDLL(str(library));lib.gesture_classify.argtypes=[ctypes.POINTER(ctypes.c_uint32),ctypes.POINTER(ctypes.c_uint32)];lib.gesture_classify.restype=ctypes.c_int
    records=[]
    for label,array in [(n,pose(n)) for n in range(1,6)]+[(3,pose(3,True)),(0,np.zeros((64,64),np.uint8))]:
        words=np.zeros(128,np.uint32)
        for i,value in enumerate(array.flat):words[i//32]|=int(value)<<(i%32)
        metrics=(ctypes.c_uint32*6)();result=lib.gesture_classify(words.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),metrics)
        records.append(dict(expected=label if label<5 else -1,result=result,metrics=list(metrics)))
        print(records[-1],flush=True)
    assert all(r['result']==r['expected'] for r in records),records
    payload=dict(result='PASS',cases=records,scope='Actual C classifier on synthetic binary silhouettes, not real-user accuracy',sources_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,Path(__file__)]})
    (out/'verification.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')


if __name__=='__main__':main()
