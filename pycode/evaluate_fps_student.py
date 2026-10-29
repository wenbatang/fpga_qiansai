"""Real held-out predictions and independent integer checks for small students."""
import argparse
import itertools
import json
import math

import numpy as np
from PIL import Image, ImageDraw, ImageOps
import torch
from torch.nn import functional as F
from torchvision.transforms.functional import to_tensor

from art6_border import integer_network
from compare_styles import font, to_image
from export_hardware import load_export
from fps_student import ROOT, RUN, RESULT, SOURCE, STYLES, LABELS, CANDIDATES, POLICY, forward, pad, sha, json_write
from hardware_network import rgb565_roundtrip
from style_network import load_network


def uint8(x):
    return torch.floor(x[0].permute(1, 2, 0).clamp(0, 1) * 255 + .5).cpu().numpy().astype(np.uint8)


def metrics(a, b):
    delta = a.astype(np.float64) / 255 - b.astype(np.float64) / 255
    mse = np.mean(delta ** 2)
    # SSIM per RGB channel, valid 11x11 Gaussian windows, sigma=1.5,
    # population covariance, K1=.01 and K2=.03. No optional library required.
    x, y = [torch.from_numpy(z).permute(2, 0, 1)[None].float().cuda() / 255 for z in (a, b)]
    kernel = torch.exp(-torch.arange(-5, 6, device=x.device).float() ** 2 / (2 * 1.5 ** 2))
    kernel = kernel / kernel.sum()
    def smooth(z):
        z = F.conv2d(z, kernel.view(1, 1, 1, 11).expand(3, 1, 1, 11), groups=3)
        return F.conv2d(z, kernel.view(1, 1, 11, 1).expand(3, 1, 11, 1), groups=3)
    mx, my = smooth(x), smooth(y)
    vx, vy, cov = smooth(x * x) - mx * mx, smooth(y * y) - my * my, smooth(x * y) - mx * my
    ssim = ((2 * mx * my + .01 ** 2) * (2 * cov + .03 ** 2) /
            ((mx * mx + my * my + .01 ** 2) * (vx + vy + .03 ** 2))).mean()
    return {'teacher_l1': float(np.mean(np.abs(delta))),
            'teacher_psnr_db': float(-10 * math.log10(max(mse, 1e-12))),
            'teacher_ssim': float(ssim),
            'spatial_std': float(np.std(a.astype(np.float64) / 255, axis=(0, 1)).mean()),
            'rgb_mean': (a.mean((0, 1)) / 255).tolist()}


def sheet(style, labels, originals, output_sets, names, path):
    w, h, gap, top = 384, 216, 12, 104
    canvas = Image.new('RGB', (gap + 4 * (w + gap), top + len(originals) * (h + 38) + 44), '#f5f3ef')
    draw = ImageDraw.Draw(canvas)
    draw.text((gap, 12), '真实留出照片 · ' + LABELS[STYLES.index(style)] + ' · 720p定点/RGB565对照', font=font(25), fill='#172b3a')
    draw.text((gap, 48), '全部为训练网络实际预测；同图同裁剪；预览缩至384×216，完整1280×720另存。', font=font(18), fill='#555555')
    for col, label in enumerate(labels):
        draw.text((gap + col * (w + gap), 77), label, font=font(18), fill='#172b3a')
    for row, original in enumerate(originals):
        items = [original, *[output_sets[key][row] for key in ('current', 'rf33', 'rf63')]]
        for col, image in enumerate(items):
            canvas.paste(image.resize((w, h), Image.Resampling.LANCZOS), (gap + col * (w + gap), top + row * (h + 38)))
        draw.text((gap, top + row * (h + 38) + h + 7), names[row], font=font(16), fill='#555555')
    draw.text((gap, canvas.height - 34), '更小模型可能损失笔触/轮廓；先看画质再决定是否移植，当前bit和四组原参数未替换。', font=font(17), fill='#555555')
    canvas.save(path)


@torch.inference_mode()
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default='refined')
    parser.add_argument('--style', nargs='+', choices=STYLES, default=list(STYLES))
    parser.add_argument('--full-integer', action='store_true', help='Additionally check one full 720p image per candidate, Van Gogh only.')
    args = parser.parse_args()
    torch.set_num_threads(4)
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    destination = RUN / args.revision if args.revision else RUN
    out = RESULT / args.revision if args.revision else RESULT
    out.mkdir(parents=True, exist_ok=True)
    split = json.loads((RUN / 'split.json').read_text(encoding='utf-8'))
    names = split['preview_holdout']
    assert not set(names) & set(split['training'])
    assert not set(names) & set(split['selection_validation'])
    originals = []
    metric_images = []
    for name in names:
        with Image.open(ROOT / 'convertpic/val2017' / name) as image:
            image = ImageOps.exif_transpose(image).convert('RGB')
            metric_images.append(ImageOps.fit(image, (384, 216), Image.Resampling.LANCZOS))
            originals.append(ImageOps.fit(image, (1280, 720), Image.Resampling.LANCZOS))
    result = {'scope': '12 development preview holdout photographs, disjoint from both training and selection validation; not a blind final benchmark.',
              'names': names, 'padding': POLICY, 'metric_geometry': [384, 216],
              'comparison_geometry': [1280, 720], 'hardware_measured': False,
              'checkpoint_deployment': 'User decision pending; production models/bitstreams unchanged.',
              'prediction_image_source': 'Actual frozen neural-network inference, never AI concept artwork.',
              'sources_sha256': {name: sha(ROOT / 'convertpic/val2017' / name) for name in names},
              'evaluation_source_sha256': sha(__file__), 'styles': {}}
    metric_input = torch.stack([to_tensor(im) for im in metric_images]).cuda()
    metric_input = rgb565_roundtrip(metric_input)
    preview_input = [rgb565_roundtrip(to_tensor(im)[None].cuda()) for im in originals[:4]]
    overview = {}
    for style in args.style:
        old_path = SOURCE / 'student' / style / 'model.pt'
        old, old_meta = load_network(old_path, 'cuda')
        old.requires_grad_(False)
        old_metric = [uint8(rgb565_roundtrip(forward(old, metric_input[i:i + 1]))) for i in range(len(metric_input))]
        output_sets = {'current': [to_image(rgb565_roundtrip(forward(old, x))[0]) for x in preview_input]}
        record = {'current_checkpoint_sha256': sha(old_path), 'current_config': old.config, 'candidates': {}}
        for candidate in CANDIDATES:
            path = destination / candidate / style / 'model.pt'
            model, meta = load_network(path, 'cuda')
            model.requires_grad_(False)
            em, layers = load_export(destination / candidate / 'export' / style)
            assert em['checkpoint_sha256'] == sha(path)
            assert em['padding'] == POLICY and not em['coordinate_phase']
            values = []
            for i in range(len(metric_input)):
                actual = uint8(rgb565_roundtrip(forward(model, metric_input[i:i + 1])))
                values.append(metrics(actual, old_metric[i]))
            output_sets[candidate] = [to_image(rgb565_roundtrip(forward(model, x))[0]) for x in preview_input]
            checks = []
            for h, w in ((31, 37), (5, 9), (1, 1)):
                rng = np.random.default_rng(20261023 + h + w)
                rgb = rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
                x = torch.from_numpy(rgb).permute(2, 0, 1)[None].float().cuda() / 255
                intermediates = []
                expected = integer_network(rgb, layers, em['monochrome'], intermediates)
                actual = uint8(forward(model, x))
                max_error = int(np.abs(expected.astype(np.int32) - actual.astype(np.int32)).max())
                assert max_error == 0, (style, candidate, h, w, max_error)
                z = torch.floor(x * 255 + .5)
                arrays = {'input_rgb': rgb, 'expected_rgb': expected, 'actual_rgb': actual}
                layer_errors = []
                for index, conv in enumerate(model.convs):
                    weights, bias, shift = model.integer_parameters(index)
                    z = F.conv2d(pad(z, conv.dilation[0]), weights, bias, dilation=conv.dilation)
                    z = torch.floor(z / 2 ** shift + .5).clamp(0, 255)
                    actual_layer = z[0].permute(1, 2, 0).cpu().numpy().astype(np.uint8)
                    delta = actual_layer.astype(np.int32) - intermediates[index].astype(np.int32)
                    error = int(np.abs(delta).max())
                    assert error == 0, (style, candidate, index, error)
                    arrays[f'expected_layer{index}'] = intermediates[index]
                    arrays[f'actual_layer{index}'] = actual_layer
                    arrays[f'delta_layer{index}'] = delta
                    layer_errors.append(error)
                case_path = out / 'integer_cases' / style / candidate / f'{w}x{h}.npz'
                case_path.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(case_path, **arrays)
                checks.append({'geometry': [w, h], 'max_abs_error': max_error, 'values': int(actual.size),
                               'layer_max_abs_errors': layer_errors, 'case_path': str(case_path), 'case_sha256': sha(case_path),
                               'layers': [{'shape': list(y.shape), 'sha256': __import__('hashlib').sha256(y.tobytes()).hexdigest()}
                                          for y in intermediates]})
            if args.full_integer and style == 'vangogh':
                x = preview_input[0]
                rgb = uint8(x)
                expected = integer_network(rgb, layers, em['monochrome'])
                actual = uint8(forward(model, x))
                max_error = int(np.abs(expected.astype(np.int32) - actual.astype(np.int32)).max())
                assert max_error == 0, (style, candidate, '720p', max_error)
                case_path = out / 'integer_cases' / style / candidate / '1280x720.npz'
                np.savez_compressed(case_path, input_rgb=rgb, expected_rgb=expected, actual_rgb=actual,
                                    delta_rgb=actual.astype(np.int32) - expected.astype(np.int32))
                checks.append({'geometry': [1280, 720], 'max_abs_error': max_error, 'values': int(actual.size),
                               'case_path': str(case_path), 'case_sha256': sha(case_path)})
            mean = {key: np.mean([v[key] for v in values], axis=0).tolist() for key in values[0]}
            weights = sum(layer['weights'].size for layer in layers)
            teacher_weights = sum(conv.weight.numel() for conv in old.convs)
            record['candidates'][candidate] = {'checkpoint_sha256': sha(path), 'checkpoint': str(path),
                                             'model_config': model.config, 'selected_epoch': meta['epoch'],
                                             'training_steps': meta['step'], 'parameters': meta['parameters'],
                                             'weight_macs_per_valid_pixel': weights,
                                             'teacher_weight_macs_per_valid_pixel': teacher_weights,
                                             'mac_reduction_factor': teacher_weights / weights,
                                             'metrics_mean': mean, 'metrics_by_photo': values,
                                             'integer_checks': checks,
                                             'anti_collapse_selection': meta.get('validation', {}),
                                             'meaning': 'Similarity to the accepted frozen teacher, not an absolute aesthetic score or measured FPGA FPS.'}
            print('EVAL', style, candidate, mean, flush=True)
            del model
        labels = ['原图', '当前12通道 / RF63', '轻量6通道 / RF33', '轻量6通道 / RF63']
        sheet(style, labels, originals[:4], output_sets, names[:4], out / (style + '_comparison.png'))
        for key, images in output_sets.items():
            folder = out / 'images' / style / key
            folder.mkdir(parents=True, exist_ok=True)
            for name, image in zip(names[:4], images):
                image.save(folder / (name.removesuffix('.jpg') + '.png'))
        overview[style] = {key: output_sets[key][0] for key in output_sets}
        result['styles'][style] = record
        json_write(out / 'evaluation.json', result)
        del old
        torch.cuda.empty_cache()
    if len(overview) == 4:
        w, h, gap, top = 384, 216, 12, 100
        image = Image.new('RGB', (gap + 4 * (w + gap), top + 4 * (h + 38) + 45), '#f5f3ef')
        draw = ImageDraw.Draw(image)
        draw.text((gap, 12), '四风格轻量化 · 真实留出照片的720p整数预测', font=font(26), fill='#172b3a')
        for i, label in enumerate(('同一原图', '当前12通道 / RF63', '6通道 / RF33（更省缓存）', '6通道 / RF63（更大感受野）')):
            draw.text((gap + i * (w + gap), 65), label, font=font(17), fill='#172b3a')
        for row, style in enumerate(STYLES):
            for col, im in enumerate([originals[0], *[overview[style][key] for key in ('current', 'rf33', 'rf63')]]):
                image.paste(im.resize((w, h), Image.Resampling.LANCZOS), (gap + col * (w + gap), top + row * (h + 38)))
            draw.text((gap, top + row * (h + 38) + h + 7), LABELS[row], font=font(17), fill='#555555')
        draw.text((gap, image.height - 33), '实际训练预测；轻量候选尚未替换板上版本，画质需用户选择。', font=font(17), fill='#555555')
        image.save(out / 'four_styles_overview.png')
    result['result'] = 'PASS_INTEGER_CHECKS_AND_REAL_PREDICTION_COMPARISON'
    json_write(out / 'evaluation.json', result)


if __name__ == '__main__':
    main()
