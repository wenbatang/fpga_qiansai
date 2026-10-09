"""Train independent style CNNs using frozen VGG19 perceptual losses."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models.vgg import make_layers

from prepare_styles import ROOT, STYLES
from style_network import StyleNetwork

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def make_split(data: Path, output: Path, seed: int, holdout: int):
    images = sorted(p for p in data.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if len(images) <= holdout:
        raise ValueError("Dataset must contain more images than the holdout size")
    random.Random(seed).shuffle(images)
    result = {"seed": seed, "data_directory": str(data.resolve()),
              "validation": [p.name for p in images[:holdout]],
              "training": [p.name for p in images[holdout:]]}
    output.mkdir(parents=True, exist_ok=True)
    split_path = output / "split.json"
    if split_path.exists():
        old = json.loads(split_path.read_text(encoding="utf-8"))
        if old != result:
            raise ValueError("Existing split differs; use a separate output directory")
    else:
        split_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


class ContentDataset(Dataset):
    def __init__(self, root: Path, filenames: list[str], size: int):
        self.paths = [root / name for name in filenames]
        self.transform = transforms.Compose([
            transforms.RandomResizedCrop(size, scale=(.5, 1.0), ratio=(.8, 1.25)),
            transforms.RandomHorizontalFlip(), transforms.ToTensor(),
        ])

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, index):
        with Image.open(self.paths[index]) as image:
            return self.transform(ImageOps.exif_transpose(image).convert("RGB"))


class VGGFeatures(nn.Module):
    def __init__(self, weights: Path):
        super().__init__()
        # VGG19 through relu4_1; classifier and later layers are not used.
        self.layers = make_layers([64, 64, "M", 128, 128, "M", 256, 256, 256, 256, "M", 512])
        state = torch.load(weights, map_location="cpu", weights_only=True)
        subset = {key.removeprefix("features."): value for key, value in state.items()
                  if key.startswith("features.") and int(key.split(".")[1]) < len(self.layers)}
        self.layers.load_state_dict(subset, strict=True)
        self.requires_grad_(False)
        self.register_buffer("mean", torch.tensor([.485, .456, .406]).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor([.229, .224, .225]).view(1, 3, 1, 1))

    def forward(self, x):
        x = (x - self.mean) / self.std
        outputs = []
        for index, layer in enumerate(self.layers):
            x = layer(x)
            if index in (3, 8, 17, 20):
                outputs.append(x)
        return outputs


def gram(x):
    # FP32 Gram products avoid overflow in mixed precision.
    batch, channels, height, width = x.shape
    with torch.autocast(device_type=x.device.type, enabled=False):
        flat = x.float().reshape(batch, channels, height * width)
        return torch.bmm(flat, flat.transpose(1, 2)) / (channels * height * width)


def seed_worker(worker_id):
    seed = torch.initial_seed() % (2 ** 32)
    np.random.seed(seed)
    random.seed(seed)


def save_checkpoint(path: Path, model, optimizer, metadata, scaler):
    data = {**metadata, "network_config": model.config,
            "model": {key: value.detach().cpu() for key, value in model.state_dict().items()},
            "optimizer": optimizer.state_dict(), "scaler": scaler.state_dict()}
    temporary = path.with_suffix(".tmp")
    torch.save(data, temporary)
    os.replace(temporary, path)


def train_one(args, name, split, vgg, device):
    seed = args.seed + list(STYLES).index(name)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    folder = args.output / name
    folder.mkdir(parents=True, exist_ok=True)
    style_path = args.styles / f"{name}.jpg"
    if not style_path.exists():
        raise FileNotFoundError(f"Run prepare_styles.py first: {style_path}")
    style_record = json.loads((args.styles / f"{name}.json").read_text(encoding="utf-8"))
    if hashlib.sha256(style_path.read_bytes()).hexdigest() != style_record["training_sha256"]:
        raise ValueError(f"Style image checksum mismatch: {style_path}")
    style_image = Image.open(style_path).convert("RGB")
    # Match the source artwork's aspect ratio; Gram matrices support differing sizes.
    style_image.thumbnail((args.style_size, args.style_size), Image.Resampling.LANCZOS)
    style = transforms.ToTensor()(style_image).unsqueeze(0).to(device)
    with torch.no_grad(), torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
        targets = [gram(feature).detach() for feature in vgg(style)]
    generator = torch.Generator().manual_seed(seed)
    dataset = ContentDataset(args.data, split["training"], args.size)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True, num_workers=args.workers,
                        pin_memory=device.type == "cuda", drop_last=False, generator=generator,
                        worker_init_fn=seed_worker, persistent_workers=args.workers > 0)
    model = StyleNetwork(args.channels, args.blocks, STYLES[name]["monochrome"]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scaler = torch.amp.GradScaler("cuda", enabled=False)  # BF16 needs no loss scaling.
    step = 0
    initial_epoch = 0
    previous_seconds = 0.
    if args.resume and (folder / "latest.pt").exists():
        checkpoint = torch.load(folder / "latest.pt", map_location=device, weights_only=True)
        if checkpoint["network_config"] != model.config or checkpoint["style_sha256"] != style_record["training_sha256"]:
            raise ValueError("Resume configuration/reference mismatch")
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        step = checkpoint["step"]
        initial_epoch = checkpoint["completed_epochs"]
        previous_seconds = checkpoint["elapsed_seconds"]
        print(f"Resuming {name} at epoch {initial_epoch}, step {step}", flush=True)
    metadata = {"style": name, "label": STYLES[name]["label"], "seed": seed,
                "style_sha256": style_record["training_sha256"], "style_source": style_record,
                "training_image_count": len(dataset), "holdout_image_count": len(split["validation"]),
                "torch_version": str(torch.__version__), "device": str(device),
                "parameters": sum(p.numel() for p in model.parameters()),
                "arguments": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
                "precision": "BF16 forward, FP32 parameters/Gram/loss" if device.type == "cuda" else "FP32"}
    metadata.update(step=step, completed_epochs=initial_epoch, elapsed_seconds=previous_seconds)
    log_path = folder / "training.csv"
    fresh_log = not args.resume or not log_path.exists()
    start = time.monotonic()
    with log_path.open("w" if fresh_log else "a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if fresh_log:
            writer.writerow(["epoch", "step", "total", "content", "style", "tv", "monochrome", "seconds"])
        for epoch in range(initial_epoch, args.epochs):
            model.train()
            totals = []
            for batch in loader:
                if args.max_steps and step >= args.max_steps:
                    break
                batch = batch.to(device, non_blocking=True)
                optimizer.zero_grad(set_to_none=True)
                with torch.no_grad(), torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
                    content_target = vgg(batch)[2].detach()
                with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
                    generated = model(batch)
                    features = vgg(generated)
                content_loss = F.mse_loss(features[2].float(), content_target.float())
                style_loss = sum(F.mse_loss(gram(feature), target.expand(batch.shape[0], -1, -1))
                                 for feature, target in zip(features, targets))
                output = generated.float()
                tv = (output[:, :, 1:] - output[:, :, :-1]).abs().mean() + (output[:, :, :, 1:] - output[:, :, :, :-1]).abs().mean()
                monochrome = (output[:, 0] - output[:, 1]).square().mean() + (output[:, 1] - output[:, 2]).square().mean()
                mono_weight = args.monochrome_weight if STYLES[name]["monochrome"] else 0.
                loss = args.content_weight * content_loss + args.style_weight * style_loss + args.tv_weight * tv + mono_weight * monochrome
                if not torch.isfinite(loss):
                    raise FloatingPointError(f"Non-finite loss at {name} step {step}")
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 10.0)
                optimizer.step()
                step += 1
                row = [epoch + 1, step, loss.item(), content_loss.item(), style_loss.item(), tv.item(), monochrome.item(), previous_seconds + time.monotonic() - start]
                writer.writerow(row)
                totals.append(row[2])
                if step == 1 or step % args.log_every == 0:
                    print(f"{name} epoch={epoch + 1} step={step} loss={row[2]:.4f} content={row[3]:.4f} style={row[4]:.7f} time={row[-1]:.1f}s", flush=True)
                    handle.flush()
                if step % 300 == 0:
                    progress = {**metadata, "step": step, "completed_epochs": epoch,
                                "elapsed_seconds": previous_seconds + time.monotonic() - start}
                    save_checkpoint(folder / "progress.pt", model, optimizer, progress, scaler)
            completed = epoch + 1 if not args.max_steps or step < args.max_steps else epoch
            metadata.update(step=step, completed_epochs=completed, elapsed_seconds=previous_seconds + time.monotonic() - start,
                            last_epoch_mean_loss=sum(totals) / len(totals) if totals else None)
            save_checkpoint(folder / "latest.pt", model, optimizer, metadata, scaler)
            if args.max_steps and step >= args.max_steps:
                break
        model.eval()
        inference = {key: value for key, value in metadata.items()}
        inference.update(network_config=model.config, model={k: v.detach().cpu() for k, v in model.state_dict().items()})
        torch.save(inference, folder / "model.pt")
        (folder / "metrics.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"FINISHED {name}: {step} steps, {metadata['parameters']:,} parameters, {metadata['elapsed_seconds']:.1f}s", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "convertpic" / "val2017")
    parser.add_argument("--styles", type=Path, default=ROOT / "styles")
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "four_styles_v1")
    parser.add_argument("--vgg-weights", type=Path, default=Path.home() / ".cache/torch/hub/checkpoints/vgg19-dcbb9e9d.pth")
    parser.add_argument("--style", nargs="+", choices=list(STYLES), default=list(STYLES))
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--size", type=int, default=256)
    parser.add_argument("--style-size", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--channels", type=int, default=16)
    parser.add_argument("--blocks", type=int, default=3)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--content-weight", type=float, default=1.)
    parser.add_argument("--style-weight", type=float, default=1e5)
    parser.add_argument("--tv-weight", type=float, default=.1)
    parser.add_argument("--monochrome-weight", type=float, default=10.)
    parser.add_argument("--seed", type=int, default=20261008)
    parser.add_argument("--holdout", type=int, default=72)
    parser.add_argument("--log-every", type=int, default=50)
    parser.add_argument("--max-steps", type=int, default=0, help="Optional short smoke/benchmark run")
    parser.add_argument("--resume", action="store_true", help="Resume a checkpoint saved at an epoch boundary")
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.size < 32:
        parser.error("epochs/batch-size must be positive; size must be at least 32")
    torch.set_num_threads(4)
    torch.backends.cudnn.benchmark = True
    torch.set_float32_matmul_precision("high")
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    print(f"Device: {device}; GPU: {torch.cuda.get_device_name(0) if device.type == 'cuda' else 'none'}", flush=True)
    split = make_split(args.data, args.output, args.seed, args.holdout)
    vgg = VGGFeatures(args.vgg_weights).to(device).eval()
    for name in args.style:
        train_one(args, name, split, vgg, device)


if __name__ == "__main__":
    main()
