"""Ten independent C6 full-resolution branches; one is active on the FPGA."""
from pathlib import Path
import importlib.util
import torch
from torch import nn
BASE=Path(__file__).resolve().parents[1]/'full720_style/network.py'
spec=importlib.util.spec_from_file_location('ten_full_resolution_base',BASE)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
pad=base.pad;rgb565=base.rgb565
class FullStyle(nn.Module):
    def __init__(self,channels=6,styles=10):
        super().__init__();self.config=dict(channels=channels,styles=styles)
        self.branches=nn.ModuleList(base.FullStyle(channels,1) for _ in range(styles));self.qat=False
    @property
    def qat(self):return self.branches[0].qat
    @qat.setter
    def qat(self,value):
        for branch in self.branches:branch.qat=value
    def freeze_bn(self):
        for branch in self.branches:branch.freeze_bn()
    def forward(self,x,style):
        if isinstance(style,int):return self.branches[style](x,0)
        out=torch.zeros_like(x)
        for slot,branch in enumerate(self.branches):
            ids=(style==slot).nonzero().flatten()
            if len(ids):out=out.index_copy(0,ids,branch(x[ids],0))
        return out
def load(path,device='cpu'):
    d=torch.load(path,map_location='cpu',weights_only=True)
    assert d['family']=='ten_independent_full_c6'
    m=FullStyle(**d['config']);m.load_state_dict(d['model']);m.qat=d.get('qat',False);m.freeze_bn()
    return m.to(device).eval(),d
