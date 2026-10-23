"""Inference-only six-style boundary fix; original trained files stay immutable.

Normal axes use reflect-101 (edge pixel not repeated). If an axis is no longer
than the layer dilation, use edge replication on that axis. This finite policy
also supports 1x1 control tests and matches the streaming row RAM remapping.
"""
from pathlib import Path
import numpy as np
import torch
from torch.nn import functional as F
from export_hardware import load_export as original_load_export

POLICY = 'reflect101; edge if axis_length<=dilation'
ROOT = Path(__file__).resolve().parent
RUN = ROOT/'runs/art6_v2'
RESULTS = ROOT/'results/art6_border_v1'


def load_export(folder):
    metadata, layers = original_load_export(folder)
    if metadata['coordinate_phase'] or len(layers)!=5:
        raise ValueError('Boundary fix applies only to the six-style RGB model')
    metadata = dict(metadata, original_training_padding=metadata['padding'],
                    padding=POLICY, inference_only_boundary_fix=True)
    return metadata, layers


def padded(x, d):
    height, width = x.shape[:2]
    x = np.pad(x, ((0, 0), (d, d), (0, 0)), mode='reflect' if width>d else 'edge')
    return np.pad(x, ((d, d), (0, 0), (0, 0)), mode='reflect' if height>d else 'edge')


def integer_network(rgb, layers, monochrome=False, intermediates=None):
    x = rgb
    for layer in layers:
        h,w,_=x.shape; d=layer['dilation']; weights=layer['weights']
        source=padded(x.astype(np.int64),d)
        acc=np.broadcast_to(layer['bias'].astype(np.int64),(h,w,len(weights))).copy()
        for ky in range(3):
            for kx in range(3):
                patch=source[ky*d:ky*d+h,kx*d:kx*d+w]
                acc+=np.einsum('hwc,oc->hwo',patch,weights[:,:,ky,kx].astype(np.int64),optimize=True)
        if acc.min()<-(2**31) or acc.max()>=2**31:raise OverflowError('int32 accumulation')
        shift=layer['shift']; x=np.clip((acc+(1<<(shift-1)))>>shift if shift else acc,0,255).astype(np.uint8)
        if intermediates is not None:intermediates.append(x.copy())
    return np.repeat(x,3,axis=2) if monochrome else x


@torch.inference_mode()
def predict(model, x):
    if not model.qat or model.config['coordinate_phase']:
        raise ValueError('Frozen RGB QAT student required')
    x=torch.floor(x.clamp(0,1)*255+.5)
    for index, conv in enumerate(model.convs):
        h,w=x.shape[-2:]; d=conv.dilation[0]
        x=F.pad(x,(d,d,0,0),mode='reflect' if w>d else 'replicate')
        x=F.pad(x,(0,0,d,d),mode='reflect' if h>d else 'replicate')
        weight,bias,shift=model.integer_parameters(index)
        x=F.conv2d(x,weight,bias,dilation=d)
        x=torch.floor(x/(2**shift)+.5).clamp(0,255)
    x=x/255
    return x.repeat(1,3,1,1) if model.config['monochrome'] else x
