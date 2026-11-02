"""Actual C RGB565 profiles + geometric classifier, using synthetic RGB ROIs.

This covers quantization and green-gain counterexamples, not real-camera
accuracy. Palette labels are explicit fixtures; no captured hand is used.
"""
from pathlib import Path
import ctypes
import hashlib
import importlib.util
import json
import os
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from desktop_process import run


def rgb565(rgb):
    r,g,b=rgb
    return ((r>>3)<<11)|((g>>2)<<5)|(b>>3)


def expand565(pixel):
    r=(pixel>>11)&31;g=(pixel>>5)&63;b=pixel&31
    return ((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2))


def old_reference(pixel):
    r,g,b=expand565(pixel)
    return int(r>=40 and g>=20 and b>=10 and r>g and r>b and r-g>8 and max(r,g,b)-min(r,g,b)>15)


def pack(bits):
    words=np.zeros(128,np.uint32)
    for i,value in enumerate(bits.flat):
        words[i//32]|=int(value)<<(i%32)
    return words


def main():
    folder=ROOT/'sim/color';folder.mkdir(parents=True,exist_ok=True)
    sources=[ROOT/'firmware/gesture_color.c',ROOT/'firmware/gesture_classify.c']
    library=folder/'gesture_color.dll'
    os.environ['PATH']='E:/software/mingw/ucrt64/bin;'+os.environ['PATH']
    temporary=folder/'temp';temporary.mkdir(exist_ok=True)
    os.environ['TMP']=os.environ['TEMP']=str(temporary)
    assert run(['E:/software/mingw/ucrt64/bin/gcc.exe','-shared','-O2','-Wall','-Wextra','-Werror',
                *map(str,sources),'-o',str(library)],folder,folder/'compile.log')==0
    lib=ctypes.CDLL(str(library))
    lib.gesture_skin565.argtypes=[ctypes.c_uint16,ctypes.c_uint]
    lib.gesture_skin565.restype=ctypes.c_uint
    lib.gesture_classify.argtypes=[ctypes.POINTER(ctypes.c_uint32),ctypes.POINTER(ctypes.c_uint32)]
    lib.gesture_classify.restype=ctypes.c_int
    fixture_source=ROOT/'sim/check_classifier.py'
    spec=importlib.util.spec_from_file_location('gesture_fixture',fixture_source)
    fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
    # Stated acceptance per profile, before consulting either C function.
    palette=[
        ('warm',(160,100,72),(1,1,1)),
        ('light',(232,184,144),(1,1,1)),
        ('dark',(80,56,32),(1,1,1)),
        ('bright',(248,232,200),(1,1,1)),
        ('moderate_green',(128,160,80),(0,1,1)),
        ('strong_green',(112,168,64),(0,0,1)),
        ('shadow_green',(64,88,24),(0,0,1)),
        ('grey',(120,120,120),(0,0,0)),
        ('white',(248,248,248),(0,0,0)),
        ('saturated_green',(16,200,16),(0,0,0)),
        ('green_background',(64,160,48),(0,0,0)),
        ('blue',(48,64,200),(0,0,0)),
    ]
    palette_records=[];pipeline_records=[]
    poses=[(1,False),(2,False),(3,False),(4,False),(3,True),(5,False)]
    for name,rgb,expected in palette:
        value=rgb565(rgb)
        accepted=tuple(int(lib.gesture_skin565(value,profile)) for profile in range(3))
        assert accepted==expected,(name,expand565(value),accepted,expected)
        palette_records.append(dict(name=name,rgb=rgb,rgb565=value,expanded=expand565(value),accepted=accepted))
        for digit,chinese in poses:
            pose=fixtures.pose(digit,chinese)
            # Constant-colour foreground on a neutral dark background. This
            # intentionally isolates segmentation from geometric recognition.
            roi=np.where(pose!=0,value,rgb565((16,16,16))).astype(np.uint16)
            for profile in range(3):
                mask=np.fromiter((lib.gesture_skin565(int(p),profile) for p in roi.flat),np.uint8,count=4096).reshape(64,64)
                words=pack(mask);metrics=(ctypes.c_uint32*6)()
                got=lib.gesture_classify(words.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),metrics)
                want=(digit if digit<5 else -1) if expected[profile] else 0
                assert got==want,(name,digit,chinese,profile,got,want,list(metrics))
                assert int(mask.sum())==(int(pose.sum()) if expected[profile] else 0)
                assert metrics[5]==(0 if want>0 else 6 if want<0 else 1)
                pipeline_records.append(dict(palette=name,digit=digit,chinese=chinese,profile=profile,
                    hits=int(mask.sum()),result=got,metrics=list(metrics)))
    # Every RGB565 input must retain the original rule in profile0, including
    # unsigned-subtraction corner cases and unknown-profile fallback.
    for value in range(65536):
        expected=old_reference(value)
        assert lib.gesture_skin565(value,0)==expected,(value,expected)
        assert lib.gesture_skin565(value,99)==expected,(value,expected)
    # Every quantized grey and pure-green intensity must be rejected by all
    # profiles, rather than only testing a single neutral example.
    for intensity in range(256):
        for rgb in [(intensity,)*3,(0,intensity,0)]:
            value=rgb565(rgb)
            assert not any(lib.gesture_skin565(value,profile) for profile in range(3)),rgb
    reason_masks=[]
    a=np.zeros((64,64),np.uint8);reason_masks.append(('empty',a,0,1))
    a=np.zeros((64,64),np.uint8);a[20:28,20:28]=1;reason_masks.append(('small_area',a,-1,2))
    a=np.zeros((64,64),np.uint8);a[16:32,8:24]=1;a[16:32,40:56]=1;reason_masks.append(('two_blobs',a,-1,3))
    a=np.zeros((64,64),np.uint8);a[10:41,0:21]=1;reason_masks.append(('clipped_left',a,-1,4))
    a=np.zeros((64,64),np.uint8);a[15:51,15:46]=1;a[18:48,18:43]=0;reason_masks.append(('thin_palm',a,-1,5))
    reason_masks.append(('five_fingers',fixtures.pose(5),-1,6))
    reason_masks.append(('valid_three',fixtures.pose(3,True),3,0))
    reason_records=[]
    for name,array,want,reason in reason_masks:
        words=pack(array);metrics=(ctypes.c_uint32*6)()
        got=lib.gesture_classify(words.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)),metrics)
        assert got==want and metrics[5]==reason,(name,got,list(metrics),want,reason)
        reason_records.append(dict(name=name,result=got,metrics=list(metrics)))
    files=[*sources,Path(__file__),fixture_source]
    result=dict(result='PASS',palette_cases=palette_records,pipeline_cases=pipeline_records,
        strict_equivalence_inputs=65536,neutral_green_intensities=512,reason_cases=reason_records,
        scope='Actual C profiles + C geometry with synthetic constant-colour RGB565 hand silhouettes; no real SC431HAI images, lighting/background robustness or user accuracy verified',
        sources_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (folder/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('PASS',len(pipeline_records),'synthetic RGB565-to-gesture cases;',
          '65536 original-rule inputs; 512 grey/pure-green intensities;',len(reason_records),'reason branches')
    print('Original strict green-hand cases reproduce result0/reason1; moderate/strong profiles recover their explicit synthetic fixtures.')


if __name__=='__main__':
    main()
