"""Exact art6 strip reference: mirror only the real frame boundary per layer."""
from pathlib import Path
import sys,numpy as np
WS=Path(__file__).resolve().parents[4];sys.path.insert(0,str(WS/'pycode'))
from art6_border import integer_network,load_export
def strip_network(rgb,layers,core_width=32,halo=32,monochrome=False):
 height,width,_=rgb.shape
 if width%core_width or halo<sum(l['dilation'] for l in layers):raise ValueError('Invalid overlap/geometry')
 output=np.empty((height,width,layers[-1]['weights'].shape[0]),np.uint8)
 for left in range(0,width,core_width):
  origin=left-halo;gx=np.arange(origin,left+core_width+halo);valid=(gx>=0)&(gx<width)
  x=np.zeros((height,len(gx),3),np.uint8);x[:,valid]=rgb[:,gx[valid]]
  for layer in layers:
   d=layer['dilation'];w=layer['weights'];acc=np.broadcast_to(layer['bias'].astype(np.int64),(height,len(gx),len(w))).copy()
   padded=np.pad(x.astype(np.int64),((d,d),(0,0),(0,0)),mode='reflect' if height>d else 'edge')
   for ky in range(3):
    for kx in range(3):
     pos=gx+(kx-1)*d
     if width>d:pos=np.where(pos<0,-pos,np.where(pos>=width,2*(width-1)-pos,pos))
     else:pos=np.clip(pos,0,width-1)
     local=pos-origin;ok=(local>=0)&(local<len(gx))
     patch=padded[ky*d:ky*d+height,np.clip(local,0,len(gx)-1)].copy();patch[:,~ok]=0
     acc+=np.einsum('hwc,oc->hwo',patch,w[:,:,ky,kx].astype(np.int64),optimize=True)
   if acc.min()<-(2**31) or acc.max()>=2**31:raise OverflowError('int32 accumulator')
   shift=layer['shift'];x=np.clip((acc+(1<<(shift-1)))>>shift if shift else acc,0,255).astype(np.uint8);x[:,~valid]=0
  output[:,left:left+core_width]=x[:,halo:halo+core_width]
 return np.repeat(output,3,axis=2) if monochrome else output
