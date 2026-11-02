"""Independent fixture perturbations for the actual already-compiled C code."""
from pathlib import Path
import ctypes,hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(Path(__file__).parent))
from check_classifier import pose
from check_runtime import packed


def main():
    lib=ctypes.CDLL(str(ROOT/'sim/classifier/classifier.dll'));lib.gesture_classify.argtypes=[ctypes.POINTER(ctypes.c_uint32),ctypes.POINTER(ctypes.c_uint32)];lib.gesture_classify.restype=ctypes.c_int
    records=[]
    for digit,chinese in [(1,False),(2,False),(3,False),(4,False),(3,True),(5,False)]:
        for mirror in [False,True]:
            for dx in [-2,0,2]:
                for dy in [0,2]:
                    source=pose(digit,chinese);source=source[:,::-1] if mirror else source
                    array=np.zeros_like(source)
                    for y in range(64):
                        for x in range(64):
                            if 0<=x+dx<64 and 0<=y+dy<64:array[y+dy,x+dx]=source[y,x]
                    words=packed(array);metrics=(ctypes.c_uint32*6)();got=lib.gesture_classify(words.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),metrics)
                    records.append(dict(digit=digit,chinese=chinese,mirror=mirror,shift=[dx,dy],result=got,expected=digit if digit<5 else -1))
    assert all(v['result']==v['expected'] for v in records),[v for v in records if v['result']!=v['expected']]
    files=[Path(__file__),ROOT/'sim/classifier/classifier.dll',ROOT/'firmware/gesture_classify.c',ROOT/'sim/check_classifier.py',ROOT/'sim/check_runtime.py']
    folder=ROOT/'sim/variants';folder.mkdir(exist_ok=True);(folder/'verification.json').write_text(json.dumps(dict(result='PASS',cases=records,scope='72 synthetic silhouette translations/mirrors; not real image accuracy',sources_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2),encoding='utf-8');print('PASS72 synthetic mirrored/translated gestures and five-finger rejection')


if __name__=='__main__':main()
