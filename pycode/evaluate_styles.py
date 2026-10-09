"""Measure held-out perceptual losses and compare with an untrained network."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from PIL import Image, ImageOps
from torch.nn import functional as F
from torchvision.transforms.functional import to_tensor

from prepare_styles import ROOT, STYLES
from style_network import StyleNetwork, load_network
from train_style import VGGFeatures, gram


@torch.inference_mode()
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=ROOT / "runs/four_styles_v1")
    parser.add_argument("--data", type=Path, default=ROOT / "convertpic/val2017")
    parser.add_argument("--styles", type=Path, default=ROOT / "styles")
    parser.add_argument("--output", type=Path, default=ROOT / "results/four_styles_v1")
    parser.add_argument("--vgg-weights", type=Path, default=Path.home() / ".cache/torch/hub/checkpoints/vgg19-dcbb9e9d.pth")
    args = parser.parse_args()
    torch.set_num_threads(4)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    split = json.loads((args.run / "split.json").read_text(encoding="utf-8"))
    assert not set(split["training"]) & set(split["validation"]), "Train/holdout leakage"
    vgg = VGGFeatures(args.vgg_weights).to(device).eval()
    report = {"validation_count": len(split["validation"]), "training_count": len(split["training"]),
              "train_holdout_overlap": 0, "device": str(device), "styles": {}}
    for name in STYLES:
        model, metadata = load_network(args.run / name / "model.pt", device)
        torch.manual_seed(metadata["seed"])
        untrained = StyleNetwork(**model.config).to(device).eval()
        style = Image.open(args.styles / f"{name}.jpg").convert("RGB")
        style.thumbnail((metadata["arguments"]["style_size"],) * 2, Image.Resampling.LANCZOS)
        targets = [gram(feature) for feature in vgg(to_tensor(style).unsqueeze(0).to(device))]
        trained_values = []
        initial_values = []
        pixel_changes = []
        size = metadata["arguments"]["size"]
        originals = []
        for filename in split["validation"]:
            with Image.open(args.data / filename) as image:
                originals.append(to_tensor(ImageOps.fit(ImageOps.exif_transpose(image).convert("RGB"), (size, size), Image.Resampling.LANCZOS)))
        for offset in range(0, len(originals), 8):
            batch = torch.stack(originals[offset:offset + 8]).to(device)
            content = vgg(batch)[2]
            for network, values in ((model, trained_values), (untrained, initial_values)):
                generated = network(batch)
                features = vgg(generated)
                content_error = F.mse_loss(features[2], content).item()
                style_error = sum(F.mse_loss(gram(feature), target.expand(batch.shape[0], -1, -1))
                                  for feature, target in zip(features, targets)).item()
                values.append((batch.shape[0], content_error, style_error))
                if network is model:
                    pixel_changes.append((batch.shape[0], (generated - batch).abs().mean().item()))
        count = len(originals)
        trained_content = sum(n * c for n, c, _ in trained_values) / count
        trained_style = sum(n * s for n, _, s in trained_values) / count
        untrained_style = sum(n * s for n, _, s in initial_values) / count
        # Warm-up and CUDA synchronization isolate batch-1 network latency.
        sample = originals[0].unsqueeze(0).to(device)
        for _ in range(5):
            model(sample)
        if device.type == "cuda":
            torch.cuda.synchronize()
        begin = time.perf_counter()
        for _ in range(30):
            model(sample)
        if device.type == "cuda":
            torch.cuda.synchronize()
        latency_ms = (time.perf_counter() - begin) / 30 * 1000
        report["styles"][name] = {"label": STYLES[name]["label"], "training_steps": metadata["step"],
                                  "parameters": metadata["parameters"], "heldout_content_mse": trained_content,
                                  "heldout_style_gram_mse": trained_style, "untrained_style_gram_mse": untrained_style,
                                  "style_loss_reduction_percent": (1 - trained_style / untrained_style) * 100,
                                  "mean_absolute_pixel_change": sum(n * v for n, v in pixel_changes) / count,
                                  "gpu_or_cpu_batch1_ms_at_256_square_fp32": latency_ms}
        print(f"{name}: held-out style error reduced {(1 - trained_style / untrained_style) * 100:.1f}%; batch-1 {latency_ms:.2f}ms", flush=True)
        del model, untrained
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "validation_metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
