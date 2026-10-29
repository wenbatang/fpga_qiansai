"""Compare frozen RF33 and C8 exports; every new file stays in build/quality.

This runs numerical software inference, never trains or opens a hardware port.
Normal RF33 pictures may be reused only with their recorded input fingerprint.
Both result columns include the FPGA's RGB565 output quantization.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import torch
from torch.nn import functional as F

PROJECT = Path(__file__).resolve().parents[1]
WORKSPACE = PROJECT.parents[2]
REFERENCE = WORKSPACE / 'style_model'
RF33 = WORKSPACE / 'pycode/runs/fps_student_v1/refined/rf33/export'
RF33_PICTURES = WORKSPACE / 'pycode/results/fps_student_v1/refined'
STYLES = ((0, 'vangogh', '梵高'), (3, 'papercut', '剪纸'),
          (4, 'comic', '漫画'), (5, 'inkwash', '水墨'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rgb565(array):
    a = np.asarray(array, dtype=np.uint8)
    r, g, b = a[..., 0] >> 3, a[..., 1] >> 2, a[..., 2] >> 3
    return np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4),
                     (b << 3) | (b >> 2)), -1)


def pad(x, d):
    x = F.pad(x, (d, d, 0, 0), mode='reflect' if x.shape[-1] > d else 'replicate')
    return F.pad(x, (0, 0, d, d), mode='reflect' if x.shape[-2] > d else 'replicate')


def tensor(array, device):
    return torch.from_numpy(array.copy()).permute(2, 0, 1)[None].to(device).float()


def array(value):
    return value[0].permute(1, 2, 0).byte().cpu().numpy()


def conv(x, layer):
    """INT8 products in float32; conservative export bound keeps sums exact."""
    if layer['w'].shape[-1] > 1:
        x = pad(x, layer['d'])
    acc = F.conv2d(x, layer['w'], layer['b'], dilation=layer['d'], groups=layer['groups'])
    shift = layer['shift'][None, :, None, None]
    out = torch.floor((acc + torch.where(shift > 0, 2. ** (shift - 1), 0.)) / 2. ** shift)
    return out.clamp(-510, 510) if layer['signed'] else out.clamp(0, 255)


def load_c8(slot, name, device):
    folder = REFERENCE / f'parameters/c8/{slot:02d}_{name}'
    meta_path = folder / 'metadata.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    source = folder / 'parameters.npz'
    assert sha(source) == meta['npz_sha256']
    values = np.load(source)
    layers = []
    for i, info in enumerate(meta['layers']):
        assert info['bound'] < 2 ** 24
        layers.append(dict(info, w=torch.tensor(values[f'w{i}'].astype(np.float32), device=device),
                           b=torch.tensor(values[f'b{i}'].astype(np.float32), device=device),
                           shift=torch.tensor(values[f'shift{i}'], device=device)))
    return layers, {'metadata': str(meta_path), 'metadata_sha256': sha(meta_path),
                    'parameters': str(source), 'parameters_sha256': sha(source),
                    'checkpoint_sha256': meta['checkpoint_sha256']}


def load_rf33(name, device):
    folder = RF33 / name
    path = folder / 'manifest.json'
    meta = json.loads(path.read_text(encoding='utf-8'))
    for filename, expected in meta['files_sha256'].items():
        assert sha(folder / filename) == expected
    assert [layer['dilation'] for layer in meta['layers']] == [1, 1, 2, 4, 8]
    assert not meta['coordinate_phase']
    values = np.load(folder / 'weights.npz')
    layers = []
    for i, info in enumerate(meta['layers']):
        w, b = values[f'w{i}'], values[f'b{i}']
        # Guard the absolute sum, not just the actual final accumulator.
        bound = int((np.abs(w.astype(np.int64)).sum((1, 2, 3)) * 255 + np.abs(b.astype(np.int64))).max())
        assert bound < 2 ** 24
        layers.append(dict(w=torch.tensor(w.astype(np.float32), device=device),
                           b=torch.tensor(b.astype(np.float32), device=device),
                           shift=torch.tensor([info['shift']] * len(b), device=device),
                           d=info['dilation'], groups=1, signed=False))
    return layers, meta['monochrome'], {'manifest': str(path), 'manifest_sha256': sha(path),
                                      'parameters_sha256': sha(folder / 'weights.npz'),
                                      'checkpoint_sha256': meta['checkpoint_sha256']}


def infer_c8(x, layers):
    h = torch.floor(F.avg_pool2d(x, 2, ceil_mode=True, count_include_pad=False) + .5)
    h = conv(h, layers[0])
    for i in (1, 3, 5, 7):
        h = (h + conv(conv(h, layers[i]), layers[i + 1])).clamp(0, 255)
    delta = conv(h, layers[9]).repeat_interleave(2, -2).repeat_interleave(2, -1)
    return (x + delta[..., :x.shape[-2], :x.shape[-1]]).clamp(0, 255)


def infer_rf33(x, layers, monochrome):
    for layer in layers:
        x = conv(x, layer)
    return x.repeat(1, 3, 1, 1) if monochrome else x


def check_references(c8, rf33, device):
    """Check the new GPU adapter against existing independent NumPy references."""
    sys.path[:0] = [str(REFERENCE), str(WORKSPACE / 'pycode')]
    spec = importlib.util.spec_from_file_location('style47_integer_reference', REFERENCE / 'integer.py')
    c8_reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c8_reference)
    from art6_border import integer_network as rf33_reference
    receipt = []
    for _, name, _ in STYLES:
        small_c8 = [dict(layer, w=layer['w'].cpu().numpy().astype(np.int8),
                         b=layer['b'].cpu().numpy().astype(np.int32),
                         shift=layer['shift'].cpu().numpy().astype(np.int32)) for layer in c8[name]]
        layers, monochrome, _ = rf33[name]
        small_rf33 = [dict(weights=l['w'].cpu().numpy().astype(np.int8),
                           bias=l['b'].cpu().numpy().astype(np.int32),
                           shift=int(l['shift'][0]), dilation=l['d']) for l in layers]
        for height, width in ((1, 1), (5, 9), (19, 22)):
            rgb = rgb565(np.random.default_rng(20261029 + height + width).integers(0, 256, (height, width, 3), dtype=np.uint8))
            x = tensor(rgb, device)
            expected_c8 = c8_reference.integer_numpy(rgb, small_c8)
            expected_rf33 = rf33_reference(rgb, small_rf33, monochrome)
            c8_error = int(np.abs(expected_c8.astype(np.int32) - array(infer_c8(x, c8[name])).astype(np.int32)).max())
            rf33_error = int(np.abs(expected_rf33.astype(np.int32) - array(infer_rf33(x, layers, monochrome)).astype(np.int32)).max())
            assert c8_error == rf33_error == 0, (name, height, width, c8_error, rf33_error)
            receipt.append(dict(style=name, geometry=[width, height], c8_max_abs_error=c8_error, rf33_max_abs_error=rf33_error))
    return dict(result='PASS', cases=receipt, scope='Small geometry integer adapter tests, not full-image NumPy or RTL verification.',
                c8_reference_sha256=sha(REFERENCE / 'integer.py'),
                rf33_reference_sha256=sha(WORKSPACE / 'pycode/art6_border.py'))


def stats(image):
    a = image.astype(np.float64)
    return dict(rgb_mean=a.mean((0, 1)).tolist(), rgb_std=a.std((0, 1)).tolist(),
                fraction_black_pixels=float(np.all(image == 0, -1).mean()),
                fraction_white_pixels=float(np.all(image == 255, -1).mean()),
                edge_l1=float((np.abs(np.diff(a, axis=0)).mean() + np.abs(np.diff(a, axis=1)).mean()) / 2))


def font(size):
    path = Path('C:/Windows/Fonts/msyh.ttc')
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default(size=size)


def sheet(path, source, predictions, caption):
    w, h, gap, top, row_h = 384, 216, 12, 112, 250
    canvas = Image.new('RGB', (3 * (w + gap) + gap, top + 4 * row_h + 44), '#f5f3ef')
    draw = ImageDraw.Draw(canvas)
    draw.text((gap, 12), '四风格 · RF33 / C8 · 真实720p定点预测', font=font(27), fill='#172b3a')
    draw.text((gap, 49), caption, font=font(18), fill='#555555')
    for col, title in enumerate(('同一原图 / RGB565', '已认可 RF33 · 六通道', '30fps候选 C8 · DW/PW')):
        draw.text((gap + col * (w + gap), 80), title, font=font(18), fill='#172b3a')
    for row, (_, name, label) in enumerate(STYLES):
        for col, picture in enumerate((source, predictions[name]['rf33'], predictions[name]['c8'])):
            im = Image.fromarray(picture).resize((w, h), Image.Resampling.LANCZOS)
            canvas.paste(im, (gap + col * (w + gap), top + row * row_h))
        draw.text((gap, top + row * row_h + h + 5), label, font=font(18), fill='#172b3a')
    draw.text((gap, canvas.height - 34), '软件输出，非板上实拍；风格相似度不等于吞吐，暗图为软件压暗而非相机曝光。', font=font(17), fill='#555555')
    canvas.save(path)


@torch.inference_mode()
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', default='cuda' if torch.cuda.is_available() else 'cpu')
    parser.add_argument('--output', type=Path, default=PROJECT / 'build/quality')
    parser.add_argument('--overwrite', action='store_true', help='Explicitly regenerate this local preview only.')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((PROJECT / 'build').resolve()):
        raise ValueError('Every generated preview must stay inside the new project build/.')
    if (output / 'comparison.json').exists() and not args.overwrite:
        raise FileExistsError('Preview already exists; use a new output or --overwrite.')
    output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    prior = json.loads((RF33_PICTURES / 'evaluation.json').read_text(encoding='utf-8'))
    report = dict(scope='Two development-preview photographs plus a synthetic 0.25-brightness stress case; not a blind benchmark.',
                  prediction_source='Frozen learned integer weights; no image generation or retraining.',
                  geometry=[1280, 720], input_format='RGB565 bit-replicated RGB uint8',
                  output_format='Both networks requantized to RGB565',
                  reference_read_only=True, board_fps_verified=False,
                  script_sha256=sha(__file__), mapping=[dict(slot=s, name=n, label=l) for s, n, l in STYLES],
                  rf33_models={}, c8_models={}, cases=[])
    c8, rf33 = {}, {}
    for slot, name, _ in STYLES:
        c8[name], report['c8_models'][name] = load_c8(slot, name, args.device)
        rf33[name] = load_rf33(name, args.device)
        report['rf33_models'][name] = rf33[name][2]
    report['adapter_reference_checks'] = check_references(c8, rf33, args.device)
    cases = [('000000220310.jpg', 1.), ('000000365208.jpg', 1.), ('000000220310.jpg', .25)]
    for filename, brightness in cases:
        original_path = WORKSPACE / 'pycode/convertpic/val2017' / filename
        assert sha(original_path) == prior['sources_sha256'][filename]
        with Image.open(original_path) as im:
            full = np.asarray(ImageOps.fit(ImageOps.exif_transpose(im).convert('RGB'), (1280, 720), Image.Resampling.LANCZOS)).copy()
        full = np.floor(full.astype(np.float64) * brightness + .5).clip(0, 255).astype(np.uint8)
        source = rgb565(full)
        case_name = Path(filename).stem + ('_dark025' if brightness < 1 else '')
        folder = output / case_name
        folder.mkdir(exist_ok=True)
        Image.fromarray(source).save(folder / 'original_rgb565.png')
        x = tensor(source, args.device)
        predictions, records = {}, {}
        for _, name, _ in STYLES:
            result_c8 = rgb565(array(infer_c8(x, c8[name])))
            cached = RF33_PICTURES / 'images' / name / 'rf33' / (Path(filename).stem + '.png')
            if brightness == 1 and cached.exists():
                result_rf33 = np.asarray(Image.open(cached).convert('RGB')).copy()
                assert result_rf33.shape == source.shape
                layers, monochrome, _ = rf33[name]
                recomputed = rgb565(array(infer_rf33(x, layers, monochrome)))
                reuse_error = int(np.abs(result_rf33.astype(np.int32) - recomputed.astype(np.int32)).max())
                assert reuse_error == 0, ('Cached RF33 picture does not match frozen export', cached, reuse_error)
                provenance = dict(reused_picture=str(cached), reused_picture_sha256=sha(cached),
                                  recomputed_same_input_max_abs_error=reuse_error)
            else:
                layers, monochrome, _ = rf33[name]
                result_rf33 = rgb565(array(infer_rf33(x, layers, monochrome)))
                provenance = dict(inference='Exact frozen RF33 exported weights in this script')
            for key, pic in (('rf33', result_rf33), ('c8', result_c8)):
                Image.fromarray(pic).save(folder / f'{name}_{key}.png')
            mse = float(np.square((result_c8.astype(np.float64) - result_rf33.astype(np.float64)) / 255).mean())
            records[name] = dict(rf33=stats(result_rf33), c8=stats(result_c8),
                                 c8_vs_rf33_psnr_db=-10 * math.log10(max(mse, 1e-12)),
                                 similarity_metric_is_not_artistic_quality=True, rf33_provenance=provenance)
            predictions[name] = dict(rf33=result_rf33, c8=result_c8)
            print('PREDICT', case_name, name, flush=True)
        preview = output / f'{case_name}_comparison.png'
        caption = '相同720p裁剪 / 同输入输出RGB565 / 预览384×216' + (' / 原图软件压暗至25%' if brightness < 1 else '')
        sheet(preview, source, predictions, caption)
        report['cases'].append(dict(name=case_name, source=str(original_path), source_sha256=sha(original_path),
                                    brightness_multiplier=brightness, preview=str(preview), preview_sha256=sha(preview),
                                    original_stats=stats(source), styles=records))
    report['files_sha256'] = {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob('*.png'))}
    (output / 'comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS quality comparison; software inference only:', output, flush=True)


if __name__ == '__main__':
    main()
