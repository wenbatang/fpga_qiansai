"""Full-resolution conditional style CNN: no pooling, resize, stride or tiles in training.

Fixed-BN/INT8 conventions match the reviewed C8 model; architecture is new.
"""
import torch
from torch import nn
from torch.nn import functional as F


def ste_round(x):return x+(torch.floor(x+.5)-x).detach()
def quant(x,scale,lo,hi):return ste_round(x/scale).clamp(lo,hi)*scale
def pad(x,d):
    x=F.pad(x,(d,d,0,0),mode='reflect' if x.shape[-1]>d else 'replicate')
    return F.pad(x,(0,0,d,d),mode='reflect' if x.shape[-2]>d else 'replicate')
def rgb565(x):
    a=torch.floor(x.clamp(0,1)*255+.5).long();r,g,b=a[:,0]>>3,a[:,1]>>2,a[:,2]>>3
    return torch.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),1).float()/255


class Layer(nn.Module):
    def __init__(self,cin,cout,k=1,d=1,groups=1,conditional=True,styles=4):
        super().__init__();self.d=d;self.k=k
        self.conv=nn.Conv2d(cin,cout,k,groups=groups,bias=False)
        self.bn=nn.BatchNorm2d(cout)
        self.affine=nn.Embedding(styles,2*cout) if conditional else None
        if self.affine is not None:
            with torch.no_grad():self.affine.weight[:,:cout].fill_(1);self.affine.weight[:,cout:].zero_()
    def forward(self,x,style,qat):
        w=self.conv.weight
        if qat:w=quant(w,w.detach().abs().amax((1,2,3),keepdim=True).clamp_min(1e-7)/127,-127,127)
        y=self.bn(F.conv2d(pad(x,self.d) if self.k>1 else x,w,dilation=self.d,groups=self.conv.groups))
        if self.affine is not None:
            a,b=self.affine(style).chunk(2,1);y=y*a[:,:,None,None]+b[:,:,None,None]
        y=y.clamp(0,6)
        return quant(y,6/255,0,255) if qat else y


class FullStyle(nn.Module):
    def __init__(self,channels=6,styles=4):
        super().__init__();self.config=dict(channels=channels,styles=styles)
        self.qat=False;self.bn_frozen=False
        self.stem=Layer(3,channels,styles=styles)
        self.blocks=nn.ModuleList(nn.ModuleList([
            Layer(channels,channels,3,d,channels,False,styles),
            Layer(channels,channels,1,styles=styles)]) for d in [1,2,4,8])
        self.head=nn.Conv2d(channels,3,1)
        nn.init.normal_(self.head.weight,0,.005);nn.init.zeros_(self.head.bias)
    def freeze_bn(self):
        self.bn_frozen=True
        for layer in self.modules():
            if isinstance(layer,nn.BatchNorm2d):layer.eval()
    def train(self,mode=True):
        super().train(mode)
        if self.bn_frozen:self.freeze_bn()
        return self
    def forward(self,x,style):
        if isinstance(style,int):style=torch.full((len(x),),style,device=x.device,dtype=torch.long)
        h=self.stem(x,style,self.qat)
        for dw,pw in self.blocks:
            h=(h+pw(dw(h,style,self.qat),style,self.qat)).clamp(0,6)
            if self.qat:h=quant(h,6/255,0,255)
        w=self.head.weight
        if self.qat:w=quant(w,w.detach().abs().amax((1,2,3),keepdim=True).clamp_min(1e-7)/127,-127,127)
        delta=F.conv2d(h,w,self.head.bias)
        if self.qat:delta=quant(delta,1/255,-510,510)
        y=(x+delta).clamp(0,1)
        return quant(y,1/255,0,255) if self.qat else y


def load(path,device='cpu'):
    data=torch.load(path,map_location='cpu',weights_only=True)
    model=FullStyle(**data['config']);model.load_state_dict(data['model'])
    model.qat=data.get('qat',False);model.freeze_bn()
    return model.to(device).eval(),data
