"""Differentiable inference exactly follows folded int8/24/shift hardware math."""
import torch
from torch.nn import functional as F
from network import FullStyle as FloatStyle,pad


def rounded(x):return x+(torch.floor(x+.5)-x).detach()
def quantized_conv(x,weight,bias,inscale,outscale,d=1,groups=1,signed=False):
    coefficient=weight*(inscale/outscale);offset=bias/outscale
    shifts=torch.floor(torch.log2(127/coefficient.detach().abs().amax((1,2,3)).clamp_min(1e-12))).clamp(0,20)
    budget=(2**21-1)-coefficient[0].numel()*127.5-.5
    magnitude=coefficient.detach().abs().sum((1,2,3))*255+offset.detach().abs()
    shifts=torch.minimum(shifts,torch.floor(torch.log2(budget/magnitude.clamp_min(1e-12))).clamp(0,20))
    scale=2.**shifts
    qw=rounded(coefficient*scale[:,None,None,None]).clamp(-127,127);qb=rounded(offset*scale)
    acc=F.conv2d(pad(x,d) if weight.shape[-1]>1 else x,qw.float(),qb.float(),dilation=d,groups=groups)
    y=rounded(acc/scale.float()[None,:,None,None])
    return y.clamp(-510,510) if signed else y.clamp(0,255)
def folded(layer):
    gain=layer.bn.weight.double()/(layer.bn.running_var.double()+layer.bn.eps).sqrt()
    bias=layer.bn.bias.double()-layer.bn.running_mean.double()*gain
    if layer.affine is not None:
        a,b=layer.affine.weight[0].double().chunk(2);gain=gain*a;bias=bias*a+b
    return layer.conv.weight.double()*gain[:,None,None,None],bias
def branch_forward(branch,x):
    with torch.autocast(x.device.type,enabled=False):
        raw=rounded(x.float().clamp(0,1)*255)
        def layer(z,module,first=False):
            w,b=folded(module)
            return quantized_conv(z,w,b,1/255 if first else 6/255,6/255,module.d,module.conv.groups)
        h=layer(raw,branch.stem,True)
        for dw,pw in branch.blocks:h=(h+layer(layer(h,dw),pw)).clamp(0,255)
        delta=quantized_conv(h,branch.head.weight.double(),branch.head.bias.double(),6/255,1/255,signed=True)
        return (raw+delta).clamp(0,255)/255


class FullStyle(FloatStyle):
    hardware_qat=True
    def forward(self,x,style):
        if isinstance(style,int):return branch_forward(self.branches[style],x)
        out=torch.zeros_like(x,dtype=torch.float32)
        for slot,branch in enumerate(self.branches):
            ids=(style==slot).nonzero().flatten()
            if len(ids):out=out.index_copy(0,ids,branch_forward(branch,x[ids]))
        return out
    @torch.no_grad()
    def project(self,limit=110.):
        changed=0
        for branch in self.branches:
            for index,layer in enumerate([branch.stem,*[part for block in branch.blocks for part in block]]):
                w,b=folded(layer);maximum=w.abs().amax((1,2,3))*(1/6 if index==0 else 1)
                factors=(limit/maximum.clamp_min(1e-12)).clamp(max=1);changed+=int((factors<1).sum());layer.bn.weight.mul_(factors)
            factors=(limit/(branch.head.weight.abs().amax((1,2,3))*6).clamp_min(1e-12)).clamp(max=1);branch.head.weight.mul_(factors[:,None,None,None])
        return changed


def load(path,device='cpu'):
    data=torch.load(path,map_location='cpu',weights_only=True);assert data['family']=='independent_full_c6'
    model=FullStyle(**data['config']);model.load_state_dict(data['model']);model.qat=True;model.freeze_bn()
    return model.to(device).eval(),data
