"""Download documented public-domain artworks for neural style training."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import requests
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
STYLES = {
    "ukiyoe": {"label": "浮世绘", "object_id": 45434, "monochrome": False},
    "vangogh": {"label": "梵高", "object_id": 436535, "monochrome": False},
    "inkwash": {"label": "水墨国画", "object_id": 49171, "monochrome": True,
                "art_crop": [.08, .17, .72, .86], "paper_autocontrast": True},
    "inkprint": {"label": "油墨版画", "object_id": 356497, "monochrome": True},
}


def prepare(output: Path, proxy: str | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    if proxy:
        session.proxies.update({"http": proxy, "https": proxy})
    manifest = {}
    for name, spec in STYLES.items():
        record_path = output / f"{name}.json"
        image_path = output / f"{name}.jpg"
        if record_path.exists() and image_path.exists():
            record = json.loads(record_path.read_text(encoding="utf-8"))
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            if digest != record["training_sha256"]:
                raise ValueError(f"Modified style image: {image_path}")
            if record.get("art_crop") == spec.get("art_crop") and record.get("paper_autocontrast") == spec.get("paper_autocontrast"):
                manifest[name] = record
                continue
        api = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{spec['object_id']}"
        response = session.get(api, timeout=60)
        response.raise_for_status()
        obj = response.json()
        if not obj["isPublicDomain"] or not obj["primaryImage"]:
            raise ValueError(f"No public-domain reference for {name}")
        response = session.get(obj["primaryImage"], timeout=120)
        response.raise_for_status()
        raw = response.content
        (output / f"{name}_source.jpg").write_bytes(raw)
        image = Image.open(io.BytesIO(raw)).convert("RGB")
        # Exclude the outer mount/frame while retaining the artwork's composition.
        w, h = image.size
        image = image.crop((round(w * .025), round(h * .025), round(w * .975), round(h * .975)))
        if "art_crop" in spec:
            w, h = image.size
            left, top, right, bottom = spec["art_crop"]
            image = image.crop((round(w * left), round(h * top), round(w * right), round(h * bottom)))
        image.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
        if spec["monochrome"]:
            image = image.convert("L")
            if spec.get("paper_autocontrast"):
                image = ImageOps.autocontrast(image, cutoff=1)
            image = image.convert("RGB")
        image.save(image_path, quality=95)
        record = {
            **spec, "name": name, "title": obj["title"], "artist": obj["artistDisplayName"],
            "source_page": obj["objectURL"], "image_url": obj["primaryImage"],
            "api_url": api, "is_public_domain": True, "license": "Met Open Access / CC0",
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "training_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "preprocessing": "2.5% outer crop; optional art_crop; maximum side 1400; grayscale RGB for ink styles; optional 1% paper autocontrast",
        }
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest[name] = record
        print(f"Prepared {name}: {image.size}, {obj['title']}", flush=True)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "styles")
    parser.add_argument("--proxy", default=None, help="Optional existing HTTP proxy URL")
    args = parser.parse_args()
    prepare(args.output, args.proxy)
