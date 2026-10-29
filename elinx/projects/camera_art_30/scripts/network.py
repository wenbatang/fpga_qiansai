"""Small conditional separable CNN; only fixed BN statistics are used at inference."""
import torch
from torch import nn
from torch.nn import functional as F

def round_ste(x):return x+(torch.floor(x+.5)-x).detach()
def quant(x,scale,lo,hi):return round_ste(x/scale).clamp(lo,hi)*scale
def pad(x,d):
    x=F.pad(x,(d,d,0,0),mode='reflect' if x.shape[-1]>d else 'replicate')
    return F.pad(x,(0,0,d,d),mode='reflect' if x.shape[-2]>d else 'replicate')
def rgb565(x):
    a=torch.floor(x.clamp(0,1)*255+.5).long();r,g,b=a[:,0]>>3,a[:,1]>>2,a[:,2]>>3
    return torch.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),1).float()/255

class ConditionalLayer(nn.Module):
    def __init__(self,cin,cout,k=3,d=1,groups=1,styles=47,conditional=True):
        super().__init__();self.d=d;self.k=k
        self.conv=nn.Conv2d(cin,cout,k,groups=groups,bias=False)
        self.bn=nn.BatchNorm2d(cout)
        self.affine=nn.Embedding(styles,2*cout) if conditional else None
        if self.affine is not None:
            with torch.no_grad():self.affine.weight[:,:cout].fill_(1);self.affine.weight[:,cout:].zero_()
    def forward(self,x,style,qat=False):
        if self.k>1:x=pad(x,self.d)
        w=self.conv.weight
        if qat:
            scale=w.detach().abs().amax((1,2,3),keepdim=True).clamp_min(1e-7)/127
            w=quant(w,scale,-127,127)
        y=F.conv2d(x,w,dilation=self.d,groups=self.conv.groups);y=self.bn(y)
        if self.affine is not None:
            a,b=self.affine(style).chunk(2,1);y=y*a[:,:,None,None]+b[:,:,None,None]
        y=y.clamp(0,6)
        return quant(y,6/255,0,255) if qat else y

class TinyStyle47(nn.Module):
    def __init__(self,channels=16,styles=47):
        super().__init__();self.config=dict(channels=channels,styles=styles);self.qat=False;self.bn_frozen=False
        self.stem=ConditionalLayer(3,channels,styles=styles)
        self.blocks=nn.ModuleList(nn.ModuleList([ConditionalLayer(channels,channels,d=d,groups=channels,styles=styles,conditional=False),ConditionalLayer(channels,channels,k=1,styles=styles)]) for d in (1,2,4,8))
        self.head=nn.Conv2d(channels,3,1)
        nn.init.normal_(self.head.weight,0,.005);nn.init.zeros_(self.head.bias)
    def freeze_bn(self):
        self.bn_frozen=True
        for m in self.modules():
            if isinstance(m,nn.BatchNorm2d):m.eval()
    def train(self,mode=True):
        super().train(mode)
        if self.bn_frozen:self.freeze_bn()
        return self
    def forward(self,x,style):
        if isinstance(style,int):style=torch.full((len(x),),style,device=x.device,dtype=torch.long)
        low=F.avg_pool2d(x,2,ceil_mode=True,count_include_pad=False)
        h=self.stem(low,style,self.qat)
        for dw,pw in self.blocks:
            z=pw(dw(h,style,self.qat),style,self.qat)
            h=(h+z).clamp(0,6)
            if self.qat:h=quant(h,6/255,0,255)
        w=self.head.weight
        if self.qat:w=quant(w,w.detach().abs().amax((1,2,3),keepdim=True).clamp_min(1e-7)/127,-127,127)
        delta=F.conv2d(h,w,self.head.bias)
        if self.qat:delta=quant(delta,1/255,-510,510)
        y=(x+F.interpolate(delta,scale_factor=2,mode='nearest')[...,:x.shape[-2],:x.shape[-1]]).clamp(0,1)
        return quant(y,1/255,0,255) if self.qat else y

def load(path,device='cpu'):
    d=torch.load(path,map_location='cpu',weights_only=True);m=TinyStyle47(**d['config']);m.load_state_dict(d['model']);m.qat=d.get('qat',False);m.freeze_bn();return m.to(device).eval(),d
