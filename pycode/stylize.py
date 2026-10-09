"""Apply one trained checkpoint to an arbitrary image at its original size."""
from __future__ import annotations

import argparse
from pathlib import Path

import torch
from PIL import Image, ImageOps
from torchvision.transforms.functional import to_tensor

from compare_styles import to_image
from prepare_styles import ROOT, STYLES
from style_network import load_network


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--style", choices=list(STYLES), required=True)
    parser.add_argument("--run", type=Path, default=ROOT / "runs" / "four_styles_v1")
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    model, _ = load_network(args.run / args.style / "model.pt", device)
    with Image.open(args.input) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    if min(image.size) < 16:
        raise ValueError("Image dimensions must be at least 16 pixels")
    with torch.inference_mode():
        result = model(to_tensor(image).unsqueeze(0).to(device))[0]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    to_image(result).save(args.output)
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
