"""Isolated small-student experiment; existing models and hardware stay immutable.

Uses HardwareNetwork only as a parameter/BN container. All training/inference
here uses per-layer reflect-101, matching the accepted art6 border policy.
"""
from pathlib import Path
import hashlib
import json

import torch
from torch.nn import functional as F

from hardware_network import HardwareNetwork, ste_round

ROOT = Path(__file__).resolve().parent
RUN = ROOT / 'runs/fps_student_v1'
RESULT = ROOT / 'results/fps_student_v1'
SOURCE = ROOT / 'runs/art6_v2'
STYLES = ('vangogh', 'papercut', 'comic', 'inkwash')
LABELS = ('梵高', '剪纸', '漫画', '水墨')
CANDIDATES = {'rf33': [1, 1, 2, 4, 8], 'rf63': [1, 2, 4, 8, 16]}
POLICY = 'reflect101; edge if axis_length<=dilation'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def pad(x, dilation):
    h, w = x.shape[-2:]
    x = F.pad(x, (dilation, dilation, 0, 0), mode='reflect' if w > dilation else 'replicate')
    return F.pad(x, (0, 0, dilation, dilation), mode='reflect' if h > dilation else 'replicate')


def forward(model, x):
    """Differentiable float/QAT path; eval QAT equals integer reflect reference."""
    if model.qat:
        x = ste_round(x.clamp(0, 1) * 255)
        for index, conv in enumerate(model.convs):
            weights, bias, shift = model.integer_parameters(index)
            x = F.conv2d(pad(x, conv.dilation[0]), weights, bias, dilation=conv.dilation)
            x = ste_round(x / 2 ** shift).clamp(0, 255)
        x = x / 255
    else:
        for index, (conv, norm) in enumerate(zip(model.convs, model.norms)):
            x = F.conv2d(pad(x, conv.dilation[0]), conv.weight, conv.bias, dilation=conv.dilation)
            x = norm(x).clamp(0, 1 if index == len(model.convs) - 1 else 6)
    return x.repeat(1, 3, 1, 1) if model.config['monochrome'] else x


def make_student(teacher, dilations):
    """Deterministic channel pruning is initialization, then all weights learn."""
    model = HardwareNetwork(channels=6, depth=5, monochrome=teacher.config['monochrome'],
                            coordinate_phase=0, dilations=dilations)
    selected = []
    for index in range(4):
        weights = teacher.convs[index + 1].weight.detach()
        importance = weights.abs().sum((0, 2, 3))
        selected.append(importance.topk(6).indices.sort().values.cpu())
    selections = [torch.arange(3), *selected, torch.arange(1 if model.config['monochrome'] else 3)]
    with torch.no_grad():
        for i, (conv, bn) in enumerate(zip(model.convs, model.norms)):
            incoming, outgoing = selections[i], selections[i + 1]
            conv.weight.copy_(teacher.convs[i].weight.detach().cpu()[outgoing][:, incoming])
            conv.bias.copy_(teacher.convs[i].bias.detach().cpu()[outgoing])
            source = teacher.norms[i].state_dict()
            bn.load_state_dict({key: value.detach().cpu()[outgoing] if value.ndim else value.detach().cpu()
                                for key, value in source.items()})
    return model, [s.tolist() for s in selected]


def export_student(checkpoint, destination):
    """Keep normal load_export schema, overriding its zero-padding label here."""
    from export_hardware import export
    manifest = export(checkpoint, destination)
    manifest.update(padding=POLICY, experiment='fps_student_v1', hardware_implemented=False)
    json_write(destination / 'manifest.json', manifest)
    return manifest
