"""Exact global-coordinate overlapping strip reference for the fixed network."""
from pathlib import Path
import sys
import numpy as np
WS=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(WS/'pycode'))
from export_hardware import integer_layer,integer_network,load_export

def strip_network(rgb,layers,core_width=320,halo=16):
    height,width,_=rgb.shape
    if width%core_width:raise ValueError('Frame width must be a multiple of core width')
    radius=sum(layer['dilation'] for layer in layers)
    if halo<radius:raise ValueError('Insufficient overlap')
    output=np.empty((height,width,layers[-1]['weights'].shape[0]),np.uint8)
    for left in range(0,width,core_width):
        gx=np.arange(left-halo,left+core_width+halo)
        valid=(gx>=0)&(gx<width)
        x=np.zeros((height,len(gx),3),np.uint8);x[:,valid]=rgb[:,gx[valid]]
        if layers[0]['weights'].shape[1]==5:
            px=np.broadcast_to((gx%4*85)[None,:],(height,len(gx))).astype(np.uint8)
            py=np.broadcast_to((np.arange(height)%4*85)[:,None],(height,len(gx))).astype(np.uint8)
            x=np.concatenate((x,px[...,None],py[...,None]),axis=2)
        x[:,~valid]=0
        for layer in layers:
            x=integer_layer(x,layer['weights'],layer['bias'],layer['shift'],layer['dilation'])
            x[:,~valid]=0
        output[:,left:left+core_width]=x[:,halo:halo+core_width]
    return output

if __name__=='__main__':
    import argparse,json
    from PIL import Image,ImageOps
    p=argparse.ArgumentParser();p.add_argument('image',type=Path);p.add_argument('--style',choices=('vangogh','ukiyoe','inkwash','oilpainting'),default='vangogh');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    meta,layers=load_export(WS/'pycode/runs/distinct_student_v1/export'/a.style)
    image=ImageOps.pad(Image.open(a.image).convert('RGB'),(1280,720),Image.Resampling.LANCZOS)
    rgb=np.asarray(image).copy();full=integer_network(rgb,layers);tiled=strip_network(rgb,layers)
    if not np.array_equal(full,tiled):raise RuntimeError('Tile/full mismatch')
    if tiled.shape[-1]==1:tiled=np.repeat(tiled,3,axis=2)
    a.output.parent.mkdir(parents=True,exist_ok=True);Image.fromarray(tiled).save(a.output)
    print(json.dumps({'shape':list(tiled.shape),'max_integer_error':0,'model_sha256':meta['checkpoint_sha256']}))
