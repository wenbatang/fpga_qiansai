"""Bit-defined full-resolution reference. No pooling or interpolation."""
import math
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
    w=(w*inscale/outscale).numpy();b=(b/outscale).numpy();weights=[];biases=[];shifts=[];bounds=[]
    for wi,bi in zip(w,b):
        shift=min(20,int(math.floor(math.log2(127/max(abs(wi).max(),1e-12)))));assert shift>=0
        while True:
            qw=np.floor(wi*2**shift+.5).clip(-127,127).astype(np.int8);qb=int(math.floor(bi*2**shift+.5))
            bound=int(np.abs(qw.astype(np.int64)).sum()*255+abs(qb))
            if bound<2**23:break
            shift-=1;assert shift>=0
        weights.append(qw);biases.append(qb);shifts.append(shift);bounds.append(bound)
    return dict(w=np.stack(weights),b=np.array(biases,np.int32),shift=np.array(shifts,np.int32),d=d,groups=groups,signed=signed,bound=max(bounds))


def model_layers(model,slot):
    layers=[]
    for i,layer in enumerate([model.stem,*[part for block in model.blocks for part in block]]):
        w,b=fold(layer,slot,model.qat)
        layers.append(pack(w,b,1/255 if i==0 else 6/255,6/255,layer.d,layer.conv.groups))
    w=model.head.weight.detach().cpu().double()
    if model.qat:
        scale=w.abs().amax((1,2,3),keepdim=True).clamp_min(1e-7)/127;w=torch.floor(w/scale+.5).clamp(-127,127)*scale
    layers.append(pack(w,model.head.bias.detach().cpu().double(),6/255,1/255,signed=True))
    return layers


def prepare_gpu(layers,device='cuda'):
    return [dict(l,w=torch.tensor(l['w'].astype(np.float32),device=device),b=torch.tensor(l['b'].astype(np.float32),device=device),shift=torch.tensor(l['shift'],device=device)) for l in layers]


def integer_torch(x,layers):
    def conv(v,l):
        if l['w'].shape[-1]>1:v=pad(v,l['d'])
        acc=F.conv2d(v,l['w'],l['b'],dilation=l['d'],groups=l['groups']);s=l['shift'][None,:,None,None]
        y=torch.floor((acc+torch.where(s>0,2.**(s-1),0))/(2.**s))
        return y.clamp(-510,510) if l['signed'] else y.clamp(0,255)
    h=conv(x,layers[0])
    for i in [1,3,5,7]:h=(h+conv(conv(h,layers[i]),layers[i+1])).clamp(0,255)
    return (x+conv(h,layers[9])).clamp(0,255)


def integer_numpy(x,layers):
    def conv(z,l):
        h,w,_=z.shape;k=l['w'].shape[-1];d=l['d'];a=np.broadcast_to(l['b'].astype(np.int64),(h,w,len(l['b']))).copy()
        if k>1:
            z=np.pad(z,((0,0),(d,d),(0,0)),mode='reflect' if w>d else 'edge');z=np.pad(z,((d,d),(0,0),(0,0)),mode='reflect' if h>d else 'edge')
        for ky in range(k):
            for kx in range(k):
                patch=z[ky*d:ky*d+h,kx*d:kx*d+w]
                if l['groups']>1:a+=patch*l['w'][:,0,ky,kx].astype(np.int64)
                else:a+=np.einsum('hwc,oc->hwo',patch,l['w'][:,:,ky,kx].astype(np.int64),optimize=True)
        s=l['shift'];q=(a+np.where(s>0,1<<np.maximum(s-1,0),0))>>s
        return q.clip(-510,510) if l['signed'] else q.clip(0,255)
    h=conv(x.astype(np.int64),layers[0])
    for i in [1,3,5,7]:h=(h+conv(conv(h,layers[i]),layers[i+1])).clip(0,255)
    return (x.astype(np.int64)+conv(h,layers[9])).clip(0,255).astype(np.uint8)
