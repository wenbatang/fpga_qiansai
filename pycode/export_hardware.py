"""Export learned int8 weights and run an independent integer reference.

Layout: output channel, input channel, row, column in Torch; FPGA memory is
tap-major, then output, input. Rounding is (acc + 2**(shift-1)) >>> shift,
including negatives; output saturates to 0..255 after every layer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

from prepare_styles import ROOT, STYLES
from prepare_distinct_styles import STYLES as DISTINCT_STYLES
from style_network import load_network


def integer_layer(x, weights, bias, shift, dilation):
    height, width, incoming = x.shape
    outgoing = weights.shape[0]
    padded = np.pad(x.astype(np.int64), ((dilation, dilation), (dilation, dilation), (0, 0)))
    accumulator = np.broadcast_to(bias.astype(np.int64), (height, width, outgoing)).copy()
    for ky in range(3):
        for kx in range(3):
            patch = padded[ky * dilation:ky * dilation + height, kx * dilation:kx * dilation + width]
            accumulator += np.einsum('hwc,oc->hwo', patch, weights[:, :, ky, kx].astype(np.int64), optimize=True)
    if accumulator.min() < -(2 ** 31) or accumulator.max() >= 2 ** 31:
        raise OverflowError("32-bit RTL accumulator overflow")
    rounded = (accumulator + (1 << (shift - 1))) >> shift if shift else accumulator
    return np.clip(rounded, 0, 255).astype(np.uint8)


def pack_taps(weights):
    """Nine ROM words; each word holds every output/input channel coefficient.

    Lane (o*Cin+i) occupies bits lane*8 +: 8. Registering this wide ROM word
    alongside the line RAM read removes weight-address arithmetic from MAC.
    """
    taps=weights.transpose(2,3,0,1).reshape(9,-1)
    return [sum((int(v)&255) << (8*i) for i,v in enumerate(row)) for row in taps]


def integer_network(rgb, layers, monochrome=False, intermediates=None):
    x = rgb
    if layers[0]['weights'].shape[1]==5:
        height,width=rgb.shape[:2]
        px=np.broadcast_to((np.arange(width)%4*85)[None,:],(height,width)).astype(np.uint8)
        py=np.broadcast_to((np.arange(height)%4*85)[:,None],(height,width)).astype(np.uint8)
        x=np.concatenate((rgb,px[...,None],py[...,None]),axis=2)
    for index, layer in enumerate(layers):
        x = integer_layer(x, layer['weights'], layer['bias'], layer['shift'], layer.get('dilation', (1, 2, 4)[min(index, 2)]))
        if intermediates is not None:
            intermediates.append(x.copy())
    return np.repeat(x, 3, axis=2) if monochrome else x


def load_export(folder):
    metadata = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    for name, digest in metadata['files_sha256'].items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Exported weight checksum mismatch: {folder / name}')
    arrays = np.load(folder / 'weights.npz')
    layers = [{'weights': arrays[f'w{i}'], 'bias': arrays[f'b{i}'], 'shift': spec['shift'], 'dilation': spec['dilation']}
              for i, spec in enumerate(metadata['layers'])]
    return metadata, layers


def export(checkpoint, folder):
    # Load/hash the same immutable bytes even if a training process publishes
    # a new best checkpoint concurrently through an atomic file replacement.
    import io
    checkpoint_bytes=checkpoint.read_bytes()
    model, metadata = load_network(io.BytesIO(checkpoint_bytes))
    if metadata.get('family') != 'dilated_int8_student' or not metadata.get('qat'):
        raise ValueError('Only validated QAT hardware students may be exported')
    model.eval()
    folder.mkdir(parents=True, exist_ok=True)
    arrays, layers = {}, []
    for index, conv in enumerate(model.convs):
        weights, bias, shift = model.integer_parameters(index)
        w = weights.detach().numpy().round().astype(np.int8)
        b = bias.detach().numpy().round().astype(np.int32)
        arrays[f'w{index}'], arrays[f'b{index}'] = w, b
        taps = w.transpose(2, 3, 0, 1).reshape(-1)
        (folder / f'layer{index}_weights.mem').write_text(''.join(f'{int(v) & 255:02x}\n' for v in taps), encoding='ascii')
        (folder / f'layer{index}_bias.mem').write_text(''.join(f'{int(v) & 0xffffffff:08x}\n' for v in b), encoding='ascii')
        layers.append({'input_channels': conv.in_channels, 'output_channels': conv.out_channels,
                       'dilation': conv.dilation[0], 'shift': shift,
                       'worst_case_abs_accumulator': int(np.abs(w.astype(np.int64)).sum((1, 2, 3)).max() * 255 + np.abs(b.astype(np.int64)).max())})
    np.savez(folder / 'weights.npz', **arrays)
    manifest = {'style': metadata['style'], 'family': metadata['family'], 'monochrome': model.config['monochrome'],
                'coordinate_phase':model.config.get('coordinate_phase',0),
                'epoch':metadata.get('epoch'),'training_steps':metadata.get('step'),
                'parameters':metadata.get('parameters'),'teacher_checkpoint_sha256':metadata.get('teacher_sha256'),
                'style_reference_sha256':metadata.get('style_sha256'),
                'coordinate_features':'x/y modulo 4 encoded as 0/85/170/255; generated in the CNN, no extra UART bytes' if model.config.get('coordinate_phase') else 'none',
                'checkpoint_sha256': hashlib.sha256(checkpoint_bytes).hexdigest(), 'layers': layers,
                'input': 'RGB uint8 interleaved; FPGA expands RGB565 using bit replication',
                'activation': 'uint8; hidden scale=6/255, input/output scale=1/255',
                'normalization': 'BatchNorm affine and running statistics folded into weights/bias',
                'padding': 'zero', 'rounding': 'floor((acc + 2^(shift-1))/2^shift)',
                'accumulator': 'signed int32; saturate each output to [0,255]'}
    manifest['files_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [*folder.glob('*.mem'),folder/'weights.npz']}
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=ROOT / 'runs/fpga_student_v2')
    parser.add_argument('--output', type=Path, default=ROOT / 'runs/fpga_student_v2/export')
    parser.add_argument('--catalog',choices=('legacy','distinct'),default='legacy')
    parser.add_argument('--style', nargs='+', choices=list(dict.fromkeys([*STYLES,*DISTINCT_STYLES])))
    parser.add_argument('--image', type=Path)
    args = parser.parse_args()
    catalog=DISTINCT_STYLES if args.catalog=='distinct' else STYLES
    args.style=args.style or list(catalog)
    if any(name not in catalog for name in args.style):parser.error('Style must belong to selected catalog')
    for name in args.style:
        folder = args.output / name
        manifest = export(args.run / name / 'model.pt', folder)
        print(f"Exported {name}: shifts={[s['shift'] for s in manifest['layers']]}")
        if args.image:
            rgb = np.asarray(ImageOps.exif_transpose(Image.open(args.image)).convert('RGB'))
            _, layers = load_export(folder)
            Image.fromarray(integer_network(rgb, layers, manifest['monochrome'])).save(folder / 'integer_preview.png')


if __name__ == '__main__':
    main()
