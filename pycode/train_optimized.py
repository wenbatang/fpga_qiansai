"""Refine existing perceptual teachers, then train and quantize FPGA students."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from torch.nn import functional as F
from torch.utils.data import DataLoader
from torchvision.transforms.functional import to_tensor

from prepare_styles import ROOT, STYLES
from prepare_distinct_styles import STYLES as DISTINCT_STYLES
from style_network import load_network
from hardware_network import HardwareNetwork, rgb565_roundtrip
from train_style import ContentDataset, VGGFeatures, gram, seed_worker


def save(path, model, metadata):
    data = {**metadata, "network_config": model.config,
            "model": {k: v.detach().cpu() for k, v in model.state_dict().items()}}
    temporary = path.with_suffix(".tmp")
    torch.save(data, temporary)
    temporary.replace(path)


def variation(x):
    return (x[..., 1:, :] - x[..., :-1, :]).abs().mean() + (x[..., :, 1:] - x[..., :, :-1]).abs().mean()


def palette_quantiles(x):
    """Differentiable RGB/opponent color distribution, independent of geometry."""
    x=F.interpolate(x.float(),size=(32,32),mode='bilinear',align_corners=False)
    r,g,b=x[:,0:1],x[:,1:2],x[:,2:3]
    return torch.cat((r,g,b,r-g,b-(r+g)/2),1).flatten(2).sort(dim=2).values


def palette_loss(x,target):
    return F.mse_loss(palette_quantiles(x),target.expand(len(x),-1,-1))


@torch.inference_mode()
def validate(model, images, vgg, targets, device, content_weight, style_weight, palette_target=None,palette_weight=0.):
    model.eval()
    totals = np.zeros(4)
    for start in range(0, len(images), 6):
        x = torch.stack(images[start:start + 6]).to(device)
        if isinstance(model,HardwareNetwork):x=rgb565_roundtrip(x)
        y = model(x)
        features, original = vgg(y), vgg(x)[2]
        content = F.mse_loss(features[2], original).item()
        style = sum(F.mse_loss(gram(f), t.expand(len(x), -1, -1)) for f, t in zip(features, targets)).item()
        palette=palette_loss(y,palette_target).item() if palette_target is not None else 0.
        totals += len(x) * np.array([content, style, variation(y).item(),palette])
    content, style, tv,palette = (totals / len(images)).tolist()
    return {"content": content, "style": style, "tv": tv,'palette':palette,
            "objective": content_weight * content + style_weight * style + .03 * tv+palette_weight*palette}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("teacher", "student"), required=True)
    parser.add_argument("--baseline", type=Path, default=ROOT / "runs/four_styles_v1")
    parser.add_argument("--teacher", type=Path, default=ROOT / "runs/optimized_teacher_v2")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--data", type=Path, default=ROOT / "convertpic/val2017")
    parser.add_argument("--styles", type=Path, default=ROOT / "styles")
    parser.add_argument('--catalog',choices=('legacy','distinct'),default='legacy')
    parser.add_argument("--style", nargs="+", choices=list(dict.fromkeys([*STYLES,*DISTINCT_STYLES])))
    parser.add_argument('--palette-weight',type=float,default=0.)
    parser.add_argument('--train-limit',type=int,default=0,help='0 means all training photos; recorded subset otherwise')
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--channels", type=int, default=8)
    parser.add_argument("--depth", type=int, choices=(3, 5), default=3)
    parser.add_argument('--coordinate-phase',type=int,choices=(0,4),default=0)
    parser.add_argument("--lr", type=float)
    parser.add_argument("--distill-weight", type=float, default=12.)
    parser.add_argument("--warm-start",type=Path)
    parser.add_argument("--qat-from-start",action="store_true")
    parser.add_argument("--straight-through-clip",action="store_true")
    parser.add_argument("--style-multiplier",type=float,default=1.)
    parser.add_argument("--feature-distill-weight",type=float,default=0.)
    parser.add_argument("--validation-limit", type=int, default=24)
    parser.add_argument("--vgg-weights", type=Path, default=Path.home() / ".cache/torch/hub/checkpoints/vgg19-dcbb9e9d.pth")
    args = parser.parse_args()
    styles=DISTINCT_STYLES if args.catalog=='distinct' else STYLES
    args.style=args.style or list(styles)
    if any(name not in styles for name in args.style):parser.error('Style must belong to selected catalog')
    if args.epochs < 3 or args.size < 32 or args.batch_size < 1 or args.validation_limit < 1:
        parser.error("epochs >= 3, size >= 32, positive batch/validation sizes required")
    args.output = args.output or ROOT / "runs" / ("optimized_teacher_v2" if args.stage == "teacher" else "fpga_student_v2")
    if args.output.resolve() in (args.baseline.resolve(), args.teacher.resolve()) and args.stage == "student":
        parser.error("Student output must be separate from teacher/baseline")
    args.output.mkdir(parents=True, exist_ok=True)
    split_bytes = (args.baseline / "split.json").read_bytes()
    split = json.loads(split_bytes)
    assert not set(split["training"]) & set(split["validation"])
    (args.output / "split.json").write_bytes(split_bytes)
    torch.set_num_threads(4)
    torch.backends.cudnn.benchmark = True
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # Gram/validation and QAT integer accumulators stay FP32.
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    vgg = VGGFeatures(args.vgg_weights).to(device).eval()
    images = []
    for name in split["validation"][:args.validation_limit]:
        with Image.open(args.data / name) as im:
            image = ImageOps.fit(ImageOps.exif_transpose(im).convert("RGB"), (args.size, args.size), Image.Resampling.LANCZOS)
            images.append(to_tensor(image))
    print(f"stage={args.stage} device={device} train={len(split['training'])} validation={len(images)}", flush=True)
    for style_index, name in enumerate(args.style):
        folder = args.output / name
        if (folder / "model.pt").exists():
            raise FileExistsError(f"Preserve completed experiment; choose a new output: {folder}")
        folder.mkdir(parents=True, exist_ok=True)
        seed = 20261012 + list(styles).index(name)
        torch.manual_seed(seed); random.seed(seed); np.random.seed(seed)
        reference_path = args.styles / f"{name}.jpg"
        record = json.loads((args.styles / f"{name}.json").read_text(encoding="utf-8"))
        if hashlib.sha256(reference_path.read_bytes()).hexdigest() != record["training_sha256"]:
            raise ValueError("Style reference changed")
        reference = Image.open(reference_path).convert("RGB")
        reference.thumbnail((512, 512), Image.Resampling.LANCZOS)
        with torch.no_grad():
            ref_tensor=to_tensor(reference).unsqueeze(0).to(device)
            targets = [gram(f) for f in vgg(ref_tensor)]
            palette_target=palette_quantiles(ref_tensor) if args.palette_weight else None
        teacher_name='vangogh' if name=='oilpainting' and args.stage=='teacher' and not (args.baseline/name/'model.pt').exists() else name
        teacher_path = (args.baseline if args.stage == "teacher" else args.teacher) / teacher_name / "model.pt"
        teacher, old = load_network(teacher_path, device)
        model = teacher if args.stage == "teacher" else HardwareNetwork(args.channels, styles[name]["monochrome"], args.depth,args.coordinate_phase).to(device)
        if args.warm_start:
            if args.stage!='student':raise ValueError('Warm start is for student refinement')
            warm_name='vangogh' if name=='oilpainting' and not (args.warm_start/name/'model.pt').exists() else name
            previous,previous_meta=load_network(args.warm_start/warm_name/'model.pt',device)
            if not previous_meta.get('qat'):raise ValueError('Warm start requires a QAT checkpoint')
            if previous.config==model.config:model.load_state_dict(previous.state_dict())
            elif {k:v for k,v in previous.config.items() if k!='coordinate_phase'}=={k:v for k,v in model.config.items() if k!='coordinate_phase'} and previous.config['coordinate_phase']==0 and model.config['coordinate_phase']==4:
                state=previous.state_dict();weight=model.convs[0].weight.detach().clone();weight.zero_();weight[:,:3]=state['convs.0.weight']
                state['convs.0.weight']=weight;model.load_state_dict(state)
            else:raise ValueError('Unsupported warm-start geometry change')
            del previous
        if args.qat_from_start:
            model.freeze_bn();model.qat=True
        model.straight_through_clip=args.straight_through_clip
        if args.stage == "student":
            teacher.requires_grad_(False)
        content_weight = .9
        style_weight = args.style_multiplier*{"ukiyoe": 150000., "vangogh": 200000., "inkwash": 130000., "inkprint": 200000.,'oilpainting':150000.}[name]
        optimizer = torch.optim.Adam(model.parameters(), lr=args.lr or (.0002 if args.stage == "teacher" else .001))
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, args.epochs, eta_min=.00002)
        training_names=split['training'][:args.train_limit] if args.train_limit else split['training']
        loader = DataLoader(ContentDataset(args.data, training_names, args.size), batch_size=args.batch_size,
                            shuffle=True, num_workers=args.workers, persistent_workers=args.workers > 0,
                            pin_memory=device.type == "cuda", worker_init_fn=seed_worker,
                            generator=torch.Generator().manual_seed(seed))
        metadata = {"style": name, "label": styles[name]["label"], "seed": seed,'generation':args.catalog,
                    "family": "perceptual_teacher" if args.stage == "teacher" else "dilated_int8_student",
                    "style_sha256": record["training_sha256"], "teacher_sha256": hashlib.sha256(teacher_path.read_bytes()).hexdigest(),
                    "parameters": sum(p.numel() for p in model.parameters()),
                    "training_images": len(training_names),'training_names':training_names, "validation_names": split["validation"][:len(images)],
                    "arguments": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                    "content_weight": content_weight, "style_weight": style_weight,
                    "selection_input": "RGB565 bit replication" if args.stage=='student' else "RGB888",
                    "precision": "FP32 CNN/integer QAT; BF16 training VGG; FP32 Gram/loss/validation"}
        metadata["arguments"]["style_size"] = 512
        if args.warm_start:metadata['warm_start_sha256']=hashlib.sha256((args.warm_start/warm_name/'model.pt').read_bytes()).hexdigest()
        baseline = validate(model, images, vgg, targets, device, content_weight, style_weight,palette_target,args.palette_weight)
        metadata["initial_validation"] = baseline
        best = baseline["objective"] if args.stage == "teacher" or args.warm_start else math.inf
        if args.stage == "teacher" or args.warm_start:
            save(folder / "model.pt", model, {**metadata, "epoch": 0, "step": 0, "validation": baseline,
                                          'qat':bool(getattr(model,'qat',False))})
        step, began = 0, time.monotonic()
        with (folder / "training.csv").open("w", newline="", encoding="utf-8") as out:
            writer = csv.writer(out)
            writer.writerow(["epoch", "step", "loss", "content", "style", "distill", "lr", "seconds"])
            for epoch in range(args.epochs):
                model.train()
                if args.stage == "student" and epoch >= max(2, args.epochs // 3):
                    model.freeze_bn(); model.qat = True
                for x in loader:
                    x = x.to(device, non_blocking=True)
                    if args.stage == "student":
                        x = rgb565_roundtrip(x)
                    optimizer.zero_grad(set_to_none=True)
                    with torch.no_grad(), torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
                        original = vgg(x)[2]
                        desired = teacher(x) if args.stage == "student" else None
                        desired_features=vgg(desired) if desired is not None and args.feature_distill_weight else None
                    generated = model(x)
                    with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
                        features = vgg(generated)
                    content = F.mse_loss(features[2].float(), original.float())
                    style = sum(F.mse_loss(gram(f), t.expand(len(x), -1, -1)) for f, t in zip(features, targets))
                    distill = F.l1_loss(generated.float(), desired.float()) if desired is not None else generated.new_zeros(())
                    feature_distill=sum(F.mse_loss(a.float(),b.float()) for a,b in zip(features,desired_features)) if desired_features is not None else generated.new_zeros(())
                    # Fine detail for print; smoother brush fields for ink wash.
                    tv_weight = .005 if name == "inkprint" else .05 if name == "inkwash" else .03
                    palette=palette_loss(generated,palette_target) if palette_target is not None else generated.new_zeros(())
                    loss = content_weight * content + style_weight * style + tv_weight * variation(generated) + args.distill_weight * distill + args.feature_distill_weight*feature_distill+args.palette_weight*palette
                    if not torch.isfinite(loss):
                        raise FloatingPointError(f"Nonfinite loss: {name}/{step}")
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 5.)
                    optimizer.step(); step += 1
                    row = [epoch + 1, step, loss.item(), content.item(), style.item(), distill.item(),
                           optimizer.param_groups[0]["lr"], time.monotonic() - began]
                    writer.writerow(row)
                    if step % 200 == 0:
                        out.flush()
                        print(f"{name} epoch={epoch+1} step={step} loss={row[2]:.4f} style={row[4]:.7f} time={row[-1]:.1f}s", flush=True)
                scheduler.step()
                scores = validate(model, images, vgg, targets, device, content_weight, style_weight,palette_target,args.palette_weight)
                meta = {**metadata, "epoch": epoch + 1, "step": step, "elapsed_seconds": time.monotonic() - began,
                        "validation": scores, "qat": bool(getattr(model, "qat", False))}
                save(folder / "latest.pt", model, meta)
                eligible = args.stage == "teacher" or model.qat
                if eligible and scores["objective"] < best:
                    best = scores["objective"]; save(folder / "model.pt", model, meta)
                print(f"VALID {name} epoch={epoch+1} {scores} best={best:.5f}", flush=True)
        (folder / "experiment.json").write_text(json.dumps({**meta, "best_objective": best}, ensure_ascii=False, indent=2), encoding="utf-8")
        del model, teacher, optimizer, loader


if __name__ == "__main__":
    main()
