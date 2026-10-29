"""Train independent six-channel RF33/RF63 students from accepted fixed teachers.

No existing checkpoint/export/RTL/bitstream is modified. Targets are actual
frozen integer teacher predictions; no generated reference image is presented
as a prediction. The original training/holdout split is preserved.
"""
import argparse
import csv
import json
import math
import random
import time

import numpy as np
from PIL import Image, ImageEnhance, ImageOps
import torch
from torch.nn import functional as F

from fps_student import ROOT, RUN, SOURCE, STYLES, CANDIDATES, POLICY, forward, make_student, export_student, sha, json_write
from hardware_network import rgb565_roundtrip
from style_network import load_network
from train_optimized import save


def prepare(args, device):
    split = json.loads((SOURCE / 'split.json').read_text(encoding='utf-8'))
    assert not set(split['training']) & set(split['validation'])
    names = random.Random(args.seed).sample(split['training'], args.train_images)
    validation = split['validation'][:24]
    preview = split['validation'][24:36]
    target = {'seed': args.seed, 'source_split_sha256': sha(SOURCE / 'split.json'),
              'training': names, 'selection_validation': validation, 'preview_holdout': preview,
              'scope': 'Development validation and preview, not an unseen final benchmark.'}
    if (RUN / 'split.json').exists():
        assert json.loads((RUN / 'split.json').read_text(encoding='utf-8')) == target
    else:
        json_write(RUN / 'split.json', target)
    cache_dir = RUN / 'cache'
    cache_dir.mkdir(exist_ok=True)
    image_path = cache_dir / 'inputs.npz'
    if image_path.exists():
        with np.load(image_path) as arrays:
            inputs, vals = arrays['training'].copy(), arrays['validation'].copy()
    else:
        def read(name, index, train):
            with Image.open(ROOT / 'convertpic/val2017' / name) as image:
                image = ImageOps.exif_transpose(image).convert('RGB')
                if train:
                    rng = random.Random(args.seed + index)
                    width, height = image.size
                    side = int(min(width, height) * rng.uniform(.65, 1.))
                    left, top = rng.randrange(width - side + 1), rng.randrange(height - side + 1)
                    image = image.crop((left, top, left + side, top + side))
                    if rng.random() < .5:
                        image = ImageOps.mirror(image)
                    if index % 5 == 0:
                        image = ImageEnhance.Brightness(image).enhance(.4 + .4 * rng.random())
                else:
                    image = ImageOps.fit(image, (min(image.size),) * 2, Image.Resampling.LANCZOS)
                return np.asarray(image.resize((args.size, args.size), Image.Resampling.LANCZOS)).copy()
        inputs = np.stack([read(name, i, True) for i, name in enumerate(names)])
        vals = np.stack([read(name, i, False) for i, name in enumerate(validation)])
        np.savez_compressed(image_path, training=inputs, validation=vals)
        json_write(cache_dir / 'sources.json', {name: sha(ROOT / 'convertpic/val2017' / name)
                                              for name in [*names, *validation]})
    assert inputs.shape == (args.train_images, args.size, args.size, 3)
    def tensor(data):
        x = torch.from_numpy(data).permute(0, 3, 1, 2).to(device)
        return torch.floor(rgb565_roundtrip(x.float() / 255) * 255 + .5).to(torch.uint8)
    return target, tensor(inputs), tensor(vals)


def target_cache(style, teacher, inputs, validation, batch):
    path = RUN / 'cache' / (style + '.npz')
    if path.exists():
        with np.load(path) as arrays:
            return tuple(torch.from_numpy(arrays[key]).to(inputs.device) for key in ('training', 'validation'))
    with torch.inference_mode():
        sets = [torch.cat([torch.floor(forward(teacher, x[i:i + batch].float() / 255) * 255 + .5).to(torch.uint8)
                           for i in range(0, len(x), batch)]) for x in (inputs, validation)]
    np.savez_compressed(path, training=sets[0].cpu().numpy(), validation=sets[1].cpu().numpy())
    print('TARGETS', style, len(inputs), len(validation), flush=True)
    return sets


def loss(y, target):
    pixel = F.l1_loss(y, target)
    coarse = F.l1_loss(F.avg_pool2d(y, 4), F.avg_pool2d(target, 4))
    edges = F.l1_loss(y[..., 1:, :] - y[..., :-1, :], target[..., 1:, :] - target[..., :-1, :])
    edges = edges + F.l1_loss(y[..., :, 1:] - y[..., :, :-1], target[..., :, 1:] - target[..., :, :-1])
    mean = F.l1_loss(y.mean((2, 3)), target.mean((2, 3)))
    # A pixel-only distillation objective can prefer a median-color collapse
    # for the strongly textured Van Gogh teacher. Explicitly preserve spatial
    # variation and image-dependent structure, without changing the teacher.
    sy, st = y.flatten(2).std(2), target.flatten(2).std(2)
    zy = (y - y.mean((2, 3), keepdim=True)) / (sy[:, :, None, None] + .03)
    zt = (target - target.mean((2, 3), keepdim=True)) / (st[:, :, None, None] + .03)
    structure = F.l1_loss(zy, zt)
    return pixel + .35 * coarse + .25 * edges + .15 * mean + .12 * structure + .4 * F.l1_loss(sy, st)


def train(args, style, candidate, teacher, inputs, validation, targets, val_targets):
    destination = RUN / args.revision if args.revision else RUN
    folder = destination / candidate / style
    if (folder / 'experiment.json').exists():
        print('PRESERVE COMPLETED', candidate, style, flush=True)
        return
    if folder.exists():
        raise FileExistsError('Incomplete experiment is retained: ' + str(folder))
    folder.mkdir(parents=True)
    seed = args.seed + STYLES.index(style) * 10 + list(CANDIDATES).index(candidate)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    model, selected = make_student(teacher, CANDIDATES[candidate])
    model.to(inputs.device)
    meta = {'family': 'dilated_int8_student', 'style': style, 'experiment': 'fps_student_v1',
            'candidate': candidate, 'padding': POLICY, 'channels': 6, 'dilations': CANDIDATES[candidate],
            'seed': seed, 'teacher_sha256': sha(SOURCE / 'student' / style / 'model.pt'),
            'style_sha256': sha(ROOT / 'styles/art6_v1' / (style + '.jpg')),
            'parameters': sum(p.numel() for p in model.parameters()), 'training_images': len(inputs),
            'selection_images': len(validation), 'training_size': args.size,
            'epochs': args.float_epochs + args.qat_epochs, 'float_epochs': args.float_epochs,
            'qat_epochs': args.qat_epochs, 'batch': args.batch, 'selected_teacher_channels': selected,
            'teacher_frozen': True, 'rgb565_input': True, 'hardware_implemented': False,
            'training_source_sha256': sha(__file__), 'helper_sha256': sha(ROOT / 'fps_student.py')}
    json_write(folder / 'configuration.json', meta)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    best = math.inf
    best_float = math.inf
    began = time.monotonic()
    step = 0
    with (folder / 'training.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['epoch', 'step', 'qat', 'training_loss', 'validation_l1', 'validation_psnr', 'seconds'])
        for epoch in range(meta['epochs']):
            if epoch == args.float_epochs:
                data = torch.load(folder / 'float_best.pt', map_location='cpu', weights_only=True)
                model.load_state_dict(data['model'])
                model.freeze_bn()
                model.qat = True
                save(folder / 'qat_initial.pt', model, {**meta, 'qat': True, 'epoch': epoch, 'step': step})
                optimizer = torch.optim.Adam(model.parameters(), lr=args.lr * .005)
                best = math.inf
            model.train()
            if not model.qat:
                progress = epoch / max(args.float_epochs - 1, 1)
                lr = args.lr * (.12 + .88 * (1 + math.cos(math.pi * progress)) / 2)
            else:
                lr = args.lr * .005 * (1 - .75 * (epoch - args.float_epochs) / max(args.qat_epochs - 1, 1))
            for group in optimizer.param_groups:
                group['lr'] = lr
            order = torch.randperm(len(inputs), device=inputs.device)
            totals = []
            for start in range(0, len(order), args.batch):
                ids = order[start:start + args.batch]
                x, target = inputs[ids].float() / 255, targets[ids].float() / 255
                optimizer.zero_grad(set_to_none=True)
                objective = loss(forward(model, x), target)
                if not torch.isfinite(objective):
                    raise FloatingPointError((style, candidate, epoch, step))
                objective.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 3.)
                optimizer.step()
                step += 1
                totals.append(float(objective.detach()))
            model.eval()
            with torch.inference_mode():
                outputs = torch.cat([forward(model, validation[i:i + args.batch].float() / 255)
                                     for i in range(0, len(validation), args.batch)])
                target = val_targets.float() / 255
                error = float(F.l1_loss(outputs, target))
                psnr = float(-10 * torch.log10(F.mse_loss(outputs, target).clamp_min(1e-12)))
                structure_objective = float(loss(outputs, target))
                variance_ratio = float(outputs.flatten(2).std(2).mean() / target.flatten(2).std(2).mean().clamp_min(1e-6))
                between_ratio = float((outputs[::2] - outputs[1::2]).abs().mean() /
                                      (target[::2] - target[1::2]).abs().mean().clamp_min(1e-6))
            current = {**meta, 'epoch': epoch + 1, 'step': step, 'qat': model.qat,
                       'elapsed_seconds': time.monotonic() - began,
                       'validation': {'teacher_l1': error, 'teacher_psnr': psnr,
                                      'structure_objective': structure_objective,
                                      'spatial_std_ratio': variance_ratio, 'between_photo_ratio': between_ratio}}
            save(folder / 'latest.pt', model, current)
            if not model.qat:
                save(folder / 'float_latest.pt', model, current)
                if structure_objective < best_float:
                    best_float = structure_objective
                    save(folder / 'float_best.pt', model, current)
            if model.qat and variance_ratio >= .4 and between_ratio >= .4 and structure_objective < best:
                best = structure_objective
                save(folder / 'model.pt', model, current)
            writer.writerow([epoch + 1, step, int(model.qat), np.mean(totals), error, psnr, current['elapsed_seconds']])
            stream.flush()
            if (epoch + 1) % 10 == 0 or model.qat or epoch == 0:
                print('VALID', candidate, style, epoch + 1, 'qat', model.qat, 'l1', round(error, 5),
                      'psnr', round(psnr, 2), 'std_ratio', round(variance_ratio, 3),
                      'seconds', round(current['elapsed_seconds']), flush=True)
    if not (folder / 'model.pt').exists():
        raise RuntimeError('Rejected: no QAT epoch passed the anti-collapse gate: ' + str(folder))
    json_write(folder / 'experiment.json', {**current, 'best_teacher_l1': best, 'checkpoint_sha256': sha(folder / 'model.pt')})
    export_student(folder / 'model.pt', destination / candidate / 'export' / style)
    del model, optimizer
    torch.cuda.empty_cache()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', nargs='+', choices=CANDIDATES, default=list(CANDIDATES))
    parser.add_argument('--style', nargs='+', choices=STYLES, default=list(STYLES))
    parser.add_argument('--train-images', type=int, default=768)
    parser.add_argument('--size', type=int, default=128)
    parser.add_argument('--batch', type=int, default=16)
    parser.add_argument('--float-epochs', type=int, default=14)
    parser.add_argument('--qat-epochs', type=int, default=8)
    parser.add_argument('--lr', type=float, default=.001)
    parser.add_argument('--seed', type=int, default=20261023)
    parser.add_argument('--revision', default='refined')
    args = parser.parse_args()
    assert torch.cuda.is_available()
    torch.set_num_threads(4)
    torch.backends.cudnn.benchmark = True
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    RUN.mkdir(parents=True, exist_ok=True)
    frozen = {str(SOURCE / 'student' / style / 'model.pt'): sha(SOURCE / 'student' / style / 'model.pt') for style in STYLES}
    json_write(RUN / 'preserved_teachers.json', frozen)
    destination = RUN / args.revision if args.revision else RUN
    destination.mkdir(parents=True, exist_ok=True)
    json_write(destination / 'launch.json', {**vars(args), 'torch': torch.__version__, 'gpu': torch.cuda.get_device_name(),
                                  'source_sha256': sha(__file__), 'helper_sha256': sha(ROOT / 'fps_student.py')})
    _, inputs, validation = prepare(args, 'cuda')
    for style in args.style:
        teacher, _ = load_network(SOURCE / 'student' / style / 'model.pt', 'cuda')
        teacher.requires_grad_(False)
        targets, val_targets = target_cache(style, teacher, inputs, validation, args.batch)
        for candidate in args.candidate:
            train(args, style, candidate, teacher, inputs, validation, targets, val_targets)
        del teacher, targets, val_targets
    assert all(sha(path) == digest for path, digest in frozen.items())
    json_write(destination / 'complete.json', {'result': 'TRAINING_COMPLETE', 'styles': args.style,
                                    'candidates': args.candidate, 'frozen_teachers_preserved': True,
                                    'hardware_implemented': False, 'user_selected_for_deployment': False})


if __name__ == '__main__':
    main()
