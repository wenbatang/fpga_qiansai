"""Dilated 3x3 convolutions with foldable BN and bounded activations.

Inference contract: RGB uint8, hidden activations uint8 representing [0,6],
output uint8 representing [0,1]. Padding is zero; depth 3 uses 1/2/4,
depth 5 uses 1/1/2/4/8. The
integer export uses a shared power-of-two weight scale for each layer.
"""
from __future__ import annotations

import math
import torch
from torch import nn
from torch.nn import functional as F


def ste_round(x):
    return x + (torch.floor(x + .5) - x).detach()


class HardwareNetwork(nn.Module):
    def __init__(self, channels=8, monochrome=False, depth=3, coordinate_phase=0, dilations=None):
        super().__init__()
        if depth not in (3, 5):
            raise ValueError("Supported streaming depths are 3 and 5")
        if coordinate_phase not in (0,4) or coordinate_phase and depth!=5:
            raise ValueError('Coordinate phase is 0 or 4 and requires depth 5')
        self.config = {"channels": channels, "monochrome": monochrome, "depth": depth,'coordinate_phase':coordinate_phase}
        widths = [5 if coordinate_phase else 3] + [channels] * (depth - 1) + [1 if monochrome else 3]
        if dilations is not None:
            if len(dilations)!=depth or any(not isinstance(d,int) or d<1 for d in dilations):
                raise ValueError('One positive integer dilation per layer required')
            self.config['dilations']=list(dilations)
        dilations = dilations or ((1, 2, 4) if depth == 3 else (1, 1, 2, 4, 8))
        self.convs = nn.ModuleList(nn.Conv2d(a, b, 3, dilation=d, padding=d)
                                   for a, b, d in zip(widths, widths[1:], dilations))
        self.norms = nn.ModuleList(nn.BatchNorm2d(c) for c in widths[1:])
        self.qat = False
        self.frozen_bn = False
        self.straight_through_clip = False

    def freeze_bn(self):
        self.frozen_bn = True
        for bn in self.norms:
            bn.eval()

    def train(self, mode=True):
        super().train(mode)
        if self.frozen_bn:
            self.freeze_bn()
        return self

    def folded(self, index):
        conv, bn = self.convs[index], self.norms[index]
        scale = bn.weight / torch.sqrt(bn.running_var + bn.eps)
        return conv.weight * scale[:, None, None, None], (conv.bias - bn.running_mean) * scale + bn.bias

    def integer_parameters(self, index):
        weight, bias = self.folded(index)
        incoming_scale = 1 / 255 if index == 0 else 6 / 255
        outgoing_scale = 1 / 255 if index == len(self.convs) - 1 else 6 / 255
        weight = weight * (incoming_scale / outgoing_scale)
        maximum = max(weight.detach().abs().max().item(), 1e-8)
        shift = min(20, math.floor(math.log2(127 / maximum)))
        if shift < 0:
            raise ValueError("Folded weights exceed int8 range; retrain before export")
        quantized_weight = ste_round(weight * 2 ** shift).clamp(-127, 127)
        quantized_bias = ste_round(bias / outgoing_scale * 2 ** shift)
        if quantized_bias.detach().abs().max().item() >= 2 ** 30:
            raise OverflowError("Export bias exceeds accumulator budget")
        bound = quantized_weight.detach().abs().sum((1, 2, 3)) * 255 + quantized_bias.detach().abs()
        if bound.max().item() >= 2 ** 24:
            raise OverflowError("QAT FP32 accumulation would no longer be integer exact")
        return quantized_weight, quantized_bias, shift

    def forward(self, x):
        if self.config['coordinate_phase']:
            height,width=x.shape[-2:]
            px=(torch.arange(width,device=x.device)%4).float()/3
            py=(torch.arange(height,device=x.device)%4).float()/3
            x=torch.cat((x,px.view(1,1,1,width).expand(len(x),1,height,width),
                         py.view(1,1,height,1).expand(len(x),1,height,width)),1)
        if self.qat:
            x = ste_round(x.clamp(0, 1) * 255)
            for index, conv in enumerate(self.convs):
                weight, bias, shift = self.integer_parameters(index)
                accumulator = F.conv2d(x, weight, bias, padding=conv.dilation, dilation=conv.dilation)
                x = ste_round(accumulator / 2 ** shift)
                clipped = x.clamp(0, 255)
                # Training-only surrogate restores gradients to clipped pixels.
                # Evaluation/export still use exactly the bounded RTL output.
                x = x + (clipped-x).detach() if self.training and self.straight_through_clip else clipped
            x = x / 255
        else:
            for index, (conv, norm) in enumerate(zip(self.convs, self.norms)):
                x = norm(conv(x)).clamp(0, 1 if index == len(self.convs) - 1 else 6)
        return x.repeat(1, 3, 1, 1) if self.config["monochrome"] else x


def rgb565_roundtrip(x):
    """Match the FPGA bit replication when expanding PC's RGB565 payload."""
    rgb = torch.floor(x.clamp(0, 1) * 255 + .5).to(torch.int64)
    r, g, b = rgb[:, 0] >> 3, rgb[:, 1] >> 2, rgb[:, 2] >> 3
    return torch.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4),
                        (b << 3) | (b >> 2)), dim=1).float() / 255
