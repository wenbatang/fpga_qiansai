"""Fold conditional fixed-BN, export signed int8 weights/int32 bias, bit-defined inference."""
import json,math
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from network import pad

def fold(layer,style,qat):
    w=layer.conv.weight.detach().cpu().double();bn=layer.bn
    if qat:
        s=w.abs().amax((1,2,3),keepdim=True).clamp_min(1e-7)/127;w=torch.floor(w/s+.5).clamp(-127,127)*s
    gain=bn.weight.detach().cpu().double()/(bn.running_var.detach().cpu().double()+bn.eps).sqrt()
    bias=bn.bias.detach().cpu().double()-bn.running_mean.detach().cpu().double()*gain
    if layer.affine is not None:
        a,b=layer.affine.weight.detach().cpu().double()[style].chunk(2);gain=gain*a;bias=bias*a+b
    return w*gain[:,None,None,None],bias

def pack(w,b,inscale,outscale,d=1,groups=1,signed=False):
    w=(w*inscale/outscale).numpy();b=(b/outscale).numpy();sh=[];weights=[];biases=[];bounds=[]
    for wi,bi in zip(w,b):
        maximum=max(abs(wi).max(),1e-12);shift=min(20,int(math.floor(math.log2(127/maximum))))
        if shift<0:raise OverflowError('Cannot represent int8 weight')
        while True:
            qw=np.floor(wi*(2**shift)+.5).clip(-127,127).astype(np.int8);qb=int(math.floor(bi*(2**shift)+.5));bound=int(np.abs(qw.astype(np.int64)).sum()*255+abs(qb))
            if bound<2**24:break
            shift-=1
            if shift<0:raise OverflowError('Accumulator exceeds exact float32 simulation budget')
        weights.append(qw);biases.append(qb);sh.append(shift);bounds.append(bound)
    return dict(w=np.stack(weights),b=np.asarray(biases,dtype=np.int32),shift=np.asarray(sh,dtype=np.int32),d=d,groups=groups,signed=signed,bound=max(bounds))

def export_model(model,dest,catalog):
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True);all_layers=[];records=[]
    for style in range(47):
        layers=[];w,b=fold(model.stem,style,model.qat);layers.append(pack(w,b,1/255,6/255))
        for dw,pw in model.blocks:
            w,b=fold(dw,style,model.qat);layers.append(pack(w,b,6/255,6/255,dw.d,dw.conv.groups))
            w,b=fold(pw,style,model.qat);layers.append(pack(w,b,6/255,6/255))
        w=model.head.weight.detach().cpu().double();b=model.head.bias.detach().cpu().double()
        if model.qat:
            s=w.abs().amax((1,2,3),keepdim=True).clamp_min(1e-7)/127;w=torch.floor(w/s+.5).clamp(-127,127)*s
        layers.append(pack(w,b,6/255,1/255,signed=True))
        arrays={f'{key}{i}':layer[key] for i,layer in enumerate(layers) for key in ('w','b','shift')}
        np.savez(dest/f'{style:02d}_{catalog[style]["name"]}.npz',**arrays)
        records.append(dict(slot=style,label=catalog[style]['label'],layers=[{k:v for k,v in layer.items() if k not in ('w','b','shift')} for layer in layers],weight_bytes=sum(l['w'].nbytes for l in layers),bias_bytes=sum(l['b'].nbytes for l in layers),shift_bytes=sum(l['shift'].nbytes for l in layers)))
        all_layers.append(layers)
    (dest/'manifest.json').write_text(json.dumps(dict(format='int8 OIHW / int32 bias / per-output power-of-two shift',rounding='floor((acc+2^(shift-1))/2^shift), including negative accumulators',activation='uint8=6/255; head signed int16=1/255 then RGB skip clamp 0..255',pool='2x2 integer mean, add n//2 before floor divide by actual pixel count; ceil at odd edge',padding='reflect101; edge if axis<=dilation',records=records,rtl_verified=False),ensure_ascii=False,indent=2),encoding='utf-8')
    return all_layers,records

def prepare_gpu(layers,device='cuda'):
    return [dict(l,w=torch.as_tensor(l['w'].astype(np.float32),device=device),b=torch.as_tensor(l['b'].astype(np.float32),device=device),shift=torch.as_tensor(l['shift'],device=device)) for l in layers]

def integer_torch(x,layers):
    """x: integral RGB NCHW float32; exact accumulations guarded by export bound < 2^24."""
    low=F.avg_pool2d(x,2,ceil_mode=True,count_include_pad=False)
    # For 1/2/4 samples and integer sums, floor(avg+.5) is round-half-up.
    h=torch.floor(low+.5)
    def conv(z,l):
        if l['w'].shape[-1]>1:z=pad(z,l['d'])
        acc=F.conv2d(z,l['w'],l['b'],dilation=l['d'],groups=l['groups'])
        sh=l['shift'][None,:,None,None];y=torch.floor((acc+torch.where(sh>0,2.**(sh-1),0.))/(2.**sh))
        return y.clamp(-510,510) if l['signed'] else y.clamp(0,255)
    h=conv(h,layers[0])
    for i in (1,3,5,7):h=(h+conv(conv(h,layers[i]),layers[i+1])).clamp(0,255)
    delta=conv(h,layers[9]);delta=delta.repeat_interleave(2,-2).repeat_interleave(2,-1)[...,:x.shape[-2],:x.shape[-1]]
    return (x+delta).clamp(0,255)

def integer_numpy(x,layers):
    """Independent int64 reference, HWC uint8, including odd and tiny axes."""
    height,width=x.shape[:2];hh=(height+1)//2;ww=(width+1)//2
    low=np.zeros((hh,ww,3),np.int64);cnt=np.zeros((hh,ww,1),np.int64)
    for dy in (0,1):
        for dx in (0,1):
            patch=x[dy::2,dx::2].astype(np.int64);low[:len(patch),:patch.shape[1]]+=patch;cnt[:len(patch),:patch.shape[1]]+=1
    h=(low+cnt//2)//cnt
    def conv(z,l):
        h,w,_=z.shape;kw=l['w'].shape[-1];d=l['d'];a=np.broadcast_to(l['b'].astype(np.int64),(h,w,len(l['b']))).copy()
        if kw>1:
            z=np.pad(z,((0,0),(d,d),(0,0)),mode='reflect' if w>d else 'edge');z=np.pad(z,((d,d),(0,0),(0,0)),mode='reflect' if h>d else 'edge')
        for ky in range(kw):
            for kx in range(kw):
                p=z[ky*d:ky*d+h,kx*d:kx*d+w]
                if l['groups']>1:a+=p*l['w'][:,0,ky,kx].astype(np.int64)
                else:a+=np.einsum('hwc,oc->hwo',p,l['w'][:,:,ky,kx].astype(np.int64),optimize=True)
        sh=l['shift'];rounded=(a+np.where(sh>0,1<<np.maximum(sh-1,0),0))>>sh
        return rounded.clip(-510,510) if l['signed'] else rounded.clip(0,255)
    h=conv(h,layers[0])
    for i in (1,3,5,7):h=(h+conv(conv(h,layers[i]),layers[i+1])).clip(0,255)
    delta=conv(h,layers[9]).repeat(2,0).repeat(2,1)[:height,:width]
    return (x.astype(np.int64)+delta).clip(0,255).astype(np.uint8)
