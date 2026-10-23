"""CPU word-write sequence for the unchanged accepted art6_v2 models."""
from pathlib import Path
import sys,numpy as np
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
sys.path.insert(0,str(WS/'pycode'))
from art6_border import load_export,integer_network
STYLES=('vangogh','papercut','comic','inkwash')
def catalog():
 models=[load_export(WS/'pycode/runs/art6_v2/export'/name) for name in STYLES]
 addresses=None;values=[]
 for meta,layers in models:
  if meta['monochrome']:
   layers[-1]['weights']=np.repeat(layers[-1]['weights'],3,axis=0)
   layers[-1]['bias']=np.repeat(layers[-1]['bias'],3)
  aa=[];vv=[]
  for i,layer in enumerate(layers):
   w=layer['weights'];cout,cin=w.shape[:2];chunks=(cin*3*8+31)//32
   for g in range((cout+2)//3):
    for tap in range(9):
     word=sum((int(w[g*3+o,c,tap//3,tap%3])&255)<<(8*(o*cin+c)) for o in range(3) for c in range(cin))
     for chunk in range(chunks):aa.append((i<<11)|((g*9+tap)<<5)|chunk);vv.append((word>>(32*chunk))&0xffffffff)
   for ch,b in enumerate(layer['bias']):aa.append(0x4000|(i<<11)|ch);vv.append(int(b)&0xffffffff)
   aa.append(0x8000|(i<<11));vv.append(int(layer['shift']))
  assert len(aa)==1217
  if addresses is not None:assert aa==addresses
  addresses=aa;values.append(vv)
 return models,addresses,values
