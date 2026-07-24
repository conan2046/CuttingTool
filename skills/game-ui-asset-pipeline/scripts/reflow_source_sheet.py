#!/usr/bin/env python3
"""Reflow visually approved flat-background candidates into declared layout slots."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hex_rgb(value: str) -> np.ndarray:
    value = value.lstrip("#")
    return np.array([int(value[index:index + 2], 16) for index in (0, 2, 4)], dtype=np.float32)


def reflow_source(
    source_path: Path,
    layout_path: Path,
    corrections_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    layout = read_json(layout_path)
    corrections = read_json(corrections_path)
    if corrections.get("approved") is not True:
        raise ValueError("corrections must be visually reviewed and approved")
    if corrections.get("classification") != "flat-background-sheet":
        raise ValueError("reflow only supports flat-background-sheet inputs")
    assets = [item for item in corrections.get("assets", []) if item.get("enabled", True)]
    slots = list(layout.get("slots", []))
    if not assets or len(assets) > len(slots):
        raise ValueError("approved candidate count must be positive and fit the layout")

    source = Image.open(source_path).convert("RGB")
    source_array = np.asarray(source, dtype=np.uint8)
    width = int(layout["layout"]["width"])
    height = int(layout["layout"]["height"])
    background = corrections["background"]
    key = hex_rgb(str(background["color"]))
    transparent = float(background.get("transparent_threshold", 12.0))
    opaque = float(background.get("opaque_threshold", 96.0))
    if opaque <= transparent:
        raise ValueError("opaque threshold must exceed transparent threshold")
    canvas = Image.new("RGB", (width, height), tuple(int(value) for value in key))
    placements: list[dict[str, Any]] = []

    for asset, slot in zip(assets, slots):
        bbox = [int(value) for value in asset["bbox"]]
        left, top, right, bottom = bbox
        if left < 0 or top < 0 or right > source.width or bottom > source.height or right <= left or bottom <= top:
            raise ValueError(f"invalid candidate bbox: {bbox}")
        crop_array = source_array[top:bottom, left:right]
        distance = np.sqrt(np.sum((crop_array.astype(np.float32) - key) ** 2, axis=2))
        alpha_array = np.clip((distance - transparent) / (opaque - transparent), 0.0, 1.0)
        alpha = Image.fromarray(np.rint(alpha_array * 255.0).astype(np.uint8), mode="L")
        crop = Image.fromarray(crop_array, mode="RGB")

        safe = slot["safe_box"]
        safe_width = int(safe["right"]) - int(safe["left"])
        safe_height = int(safe["bottom"]) - int(safe["top"])
        scale = min(1.0, safe_width / crop.width, safe_height / crop.height)
        if scale < 1.0:
            size = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
            crop = crop.resize(size, Image.Resampling.LANCZOS)
            alpha = alpha.resize(size, Image.Resampling.LANCZOS)
        x = int(safe["left"]) + (safe_width - crop.width) // 2
        y = int(safe["top"]) + (safe_height - crop.height) // 2
        canvas.paste(crop, (x, y), alpha)
        placements.append(
            {
                "source_index": int(asset["source_index"]),
                "slot_index": int(slot["index"]),
                "source_bbox": bbox,
                "output_bbox": [x, y, x + crop.width, y + crop.height],
                "scale": round(scale, 6),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return {
        "schema_version": 1,
        "ok": True,
        "source": str(source_path),
        "source_sha256": sha256(source_path),
        "output": str(output_path),
        "output_sha256": sha256(output_path),
        "canvas": [width, height],
        "candidate_count": len(assets),
        "placements": placements,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--layout-json", required=True, type=Path)
    parser.add_argument("--corrections", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = reflow_source(
            args.input.expanduser().resolve(),
            args.layout_json.expanduser().resolve(),
            args.corrections.expanduser().resolve(),
            args.output.expanduser().resolve(),
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.error(str(error))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
