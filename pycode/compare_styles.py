"""Render held-out comparison sheets: originals above feed-forward predictions."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont, ImageOps
from torchvision.transforms.functional import to_tensor

from prepare_styles import ROOT, STYLES
from style_network import load_network


def font(size: int):
    for candidate in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/arial.ttf"):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def to_image(tensor):
    array = (tensor.detach().float().cpu().clamp(0, 1).permute(1, 2, 0).numpy() * 255).round().astype(np.uint8)
    return Image.fromarray(array)


@torch.inference_mode()
def predict(model, images, device):
    batch = torch.stack([to_tensor(image) for image in images]).to(device)
    return [to_image(item) for item in model(batch)]


def sheet(originals, predictions, reference, label, page, total_pages, names, size=240):
    columns = 6
    gap = 8
    margin = 48
    top = 86
    block_h = 2 * size + 50
    canvas = Image.new("RGB", (margin + columns * (size + gap) + 16, top + 2 * block_h + 18), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 20), f"风格「{label}」前馈网络效果（第 {page}/{total_pages} 批）", font=font(26), fill="black")
    draw.text((margin, 53), f"每块上排原图、下排风格化；本批 {len(originals)} 组，来自训练留出集", font=font(19), fill="#555555")
    thumb = ImageOps.contain(reference, (66, 66))
    canvas.paste(thumb, (canvas.width - 84, 8))
    for index, (original, styled) in enumerate(zip(originals, predictions)):
        block, column = divmod(index, columns)
        x = margin + column * (size + gap)
        y = top + block * block_h
        canvas.paste(original.resize((size, size), Image.Resampling.LANCZOS), (x, y))
        canvas.paste(styled.resize((size, size), Image.Resampling.LANCZOS), (x, y + size + gap))
        draw.text((x, y + 2 * size + gap + 3), Path(names[index]).stem, font=font(12), fill="#555555")
        if column == 0:
            draw.text((4, y + size // 2 - 10), "原图", font=font(17), fill="#2539a5")
            draw.text((2, y + size + gap + size // 2 - 10), "风格化", font=font(14), fill="#b52b2b")
    return canvas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=ROOT / "runs" / "four_styles_v1")
    parser.add_argument("--data", type=Path, default=ROOT / "convertpic" / "val2017")
    parser.add_argument("--styles", type=Path, default=ROOT / "styles")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "four_styles_v1")
    parser.add_argument("--style", nargs="+", choices=list(STYLES), default=list(STYLES))
    parser.add_argument("--limit", type=int, default=72)
    parser.add_argument("--size", type=int, default=256)
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    torch.set_num_threads(4)
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    split = json.loads((args.run / "split.json").read_text(encoding="utf-8"))
    names = split["validation"][:args.limit]
    if not names:
        raise ValueError("No validation images selected")
    originals = []
    for name in names:
        with Image.open(args.data / name) as image:
            originals.append(ImageOps.fit(ImageOps.exif_transpose(image).convert("RGB"), (args.size, args.size), Image.Resampling.LANCZOS))
    args.output.mkdir(parents=True, exist_ok=True)
    summary = {}
    overview_outputs = {}
    for style_name in args.style:
        model, metadata = load_network(args.run / style_name / "model.pt", device)
        destination = args.output / style_name
        destination.mkdir(parents=True, exist_ok=True)
        reference = Image.open(args.styles / f"{style_name}.jpg").convert("RGB")
        predictions = []
        started = time.perf_counter()
        for offset in range(0, len(originals), 8):
            predictions.extend(predict(model, originals[offset:offset + 8], device))
        elapsed = time.perf_counter() - started
        pages = (len(names) + 11) // 12
        for index, prediction in enumerate(predictions):
            prediction.save(destination / f"{Path(names[index]).stem}_styled.png")
        for offset in range(0, len(names), 12):
            page = offset // 12 + 1
            canvas = sheet(originals[offset:offset + 12], predictions[offset:offset + 12], reference,
                           STYLES[style_name]["label"], page, pages, names[offset:offset + 12])
            canvas.save(destination / f"comparison_{page:02d}.jpg", quality=95)
        overview_outputs[style_name] = predictions[:6]
        summary[style_name] = {"images": len(names), "comparison_pages": pages, "training_steps": metadata["step"],
                               "parameters": metadata["parameters"], "render_seconds_including_cpu_transfer": elapsed}
        print(f"Rendered {style_name}: {len(names)} images, {pages} sheets", flush=True)
        del model
    # A compact common-content view helps compare the four distinct styles.
    cell = 190
    margin = 92
    row_h = cell + 18
    overview = Image.new("RGB", (margin + 6 * (cell + 6) + 12, 60 + (len(args.style) + 1) * row_h), "white")
    draw = ImageDraw.Draw(overview)
    draw.text((margin, 13), f"{len(args.style)} 种风格 · 同一组留出图片 · 神经网络推理对比", font=font(24), fill="black")
    for row, (label, imgs) in enumerate([("原图", originals[:6])] + [(STYLES[name]["label"], overview_outputs[name]) for name in args.style]):
        y = 60 + row * row_h
        draw.text((4, y + cell // 2 - 10), label, font=font(19), fill="#333333")
        for column, image in enumerate(imgs):
            overview.paste(image.resize((cell, cell), Image.Resampling.LANCZOS), (margin + column * (cell + 6), y))
    overview.save(args.output / "overview_four_styles.jpg", quality=95)
    (args.output / "evaluation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
