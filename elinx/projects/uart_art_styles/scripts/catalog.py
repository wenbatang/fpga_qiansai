"""Immutable art6 weights, folded ROM layout, and selected physical-key slots."""
from pathlib import Path
import sys,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[1];WS=ROOT.parents[2]
sys.path.insert(0,str(WS/'pycode'))
from art6_border import load_export,POLICY
ALL=('vangogh','monet','ukiyoe','papercut','comic','inkwash')
SELECTED=('vangogh','papercut','comic','inkwash')
LABELS={'vangogh':'梵高厚涂','monet':'莫奈印象派','ukiyoe':'浮世绘','papercut':'彩色剪纸','comic':'复古漫画','inkwash':'水墨'}
LANES=3;CORE=32;HALO=32
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def weights(folder,styles=SELECTED):
 folder.mkdir(parents=True,exist_ok=True)
 loaded=[load_export(WS/'pycode/runs/art6_v2/export'/name) for name in styles]
 for meta,network in loaded:
  assert meta['padding']==POLICY and [l['dilation'] for l in network]==[1,2,4,8,16]
  if meta['monochrome']:
   network[-1]['weights']=np.repeat(network[-1]['weights'],3,axis=0)
   network[-1]['bias']=np.repeat(network[-1]['bias'],3)
 for i in range(5):
  cin=loaded[0][1][i]['weights'].shape[1];cout=loaded[0][1][i]['weights'].shape[0]
  groups=(cout+LANES-1)//LANES;words=[];bias=[]
  for meta,network in loaded:
   w=network[i]['weights'];b=network[i]['bias']
   for g in range(groups):
    for tap in range(9):
     word=0
     for o in range(LANES):
      for c in range(cin):
       value=int(w[g*LANES+o,c,tap//3,tap%3]) if g*LANES+o<cout else 0
       word|=(value&255)<<(8*(o*cin+c))
     words.append(f'{word:0{cin*LANES*2}x}\n')
    word=sum((int(b[g*LANES+o])&0xffffffff)<<(32*o) for o in range(LANES) if g*LANES+o<cout)
    bias.append(f'{word:0{LANES*8}x}\n')
  (folder/f'w{i}.mem').write_text(''.join(words),encoding='ascii')
  (folder/f'b{i}.mem').write_text(''.join(bias),encoding='ascii')
  (folder/f's{i}.mem').write_text(''.join(f'{l[i]["shift"]:02x}\n' for _,l in loaded),encoding='ascii')
 return [m for m,_ in loaded]
