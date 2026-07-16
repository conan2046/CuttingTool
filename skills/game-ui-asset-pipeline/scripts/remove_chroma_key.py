#!/usr/bin/env python3
"""Convert a flat chroma-key background to alpha and decontaminate edge RGB."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def parse_hex_color(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"#?([0-9A-Fa-f]{6})", value.strip())
    if not match:
        raise argparse.ArgumentTypeError("color must use #RRGGBB format")
    encoded = match.group(1)
    return tuple(int(encoded[index : index + 2], 16) for index in (0, 2, 4))


def format_hex(color: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{channel:02X}" for channel in color)


def sample_border_key(rgb: np.ndarray, border_width: int = 8) -> tuple[int, int, int]:
    height, width, _ = rgb.shape
    border_width = max(1, min(border_width, max(1, min(height, width) // 4)))
    samples = np.concatenate(
        [
            rgb[:border_width, :, :].reshape(-1, 3),
            rgb[-border_width:, :, :].reshape(-1, 3),
            rgb[:, :border_width, :].reshape(-1, 3),
            rgb[:, -border_width:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    median = np.median(samples, axis=0)
    return tuple(int(round(value)) for value in median)


def remove_chroma(
    source: Image.Image,
    key: tuple[int, int, int],
    transparent_threshold: float = 12.0,
    opaque_threshold: float = 96.0,
    despill: bool = True,
) -> tuple[Image.Image, dict[str, Any]]:
    if transparent_threshold < 0:
        raise ValueError("transparent_threshold must be non-negative")
    if opaque_threshold <= transparent_threshold:
        raise ValueError("opaque_threshold must be greater than transparent_threshold")

    rgba = np.asarray(source.convert("RGBA"), dtype=np.float32)
    rgb = rgba[:, :, :3]
    original_alpha = rgba[:, :, 3] / 255.0
    key_array = np.asarray(key, dtype=np.float32).reshape(1, 1, 3)
    distance = np.linalg.norm(rgb - key_array, axis=2)

    matte = np.clip(
        (distance - transparent_threshold) / (opaque_threshold - transparent_threshold),
        0.0,
        1.0,
    )
    alpha = original_alpha * matte

    cleaned_rgb = rgb.copy()
    if despill:
        recoverable = (alpha > 1.0 / 255.0) & (alpha < 0.999)
        alpha_safe = np.maximum(alpha[:, :, None], 1.0 / 255.0)
        estimated_foreground = (rgb - (1.0 - alpha[:, :, None]) * key_array) / alpha_safe
        estimated_foreground = np.clip(estimated_foreground, 0.0, 255.0)
        cleaned_rgb[recoverable] = estimated_foreground[recoverable]

    transparent = alpha <= 1.0 / 255.0
    cleaned_rgb[transparent] = 0.0
    output_array = np.empty_like(rgba, dtype=np.uint8)
    output_array[:, :, :3] = np.rint(np.clip(cleaned_rgb, 0.0, 255.0)).astype(np.uint8)
    output_array[:, :, 3] = np.rint(alpha * 255.0).astype(np.uint8)
    output = Image.fromarray(output_array, mode="RGBA")

    key_distance_after = np.linalg.norm(output_array[:, :, :3].astype(np.float32) - key_array, axis=2)
    visible = output_array[:, :, 3] > 0
    near_key_visible = visible & (key_distance_after <= transparent_threshold)
    report = {
        "schema_version": 1,
        "ok": int(np.count_nonzero(near_key_visible)) == 0,
        "algorithm": "rgb-distance-soft-matte-with-foreground-recovery",
        "chroma_key": format_hex(key),
        "transparent_threshold": transparent_threshold,
        "opaque_threshold": opaque_threshold,
        "despill": despill,
        "width": output.width,
        "height": output.height,
        "transparent_pixels": int(np.count_nonzero(output_array[:, :, 3] == 0)),
        "partial_alpha_pixels": int(np.count_nonzero((output_array[:, :, 3] > 0) & (output_array[:, :, 3] < 255))),
        "opaque_pixels": int(np.count_nonzero(output_array[:, :, 3] == 255)),
        "visible_near_key_pixels": int(np.count_nonzero(near_key_visible)),
    }
    return output, report


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    key_group = parser.add_mutually_exclusive_group(required=True)
    key_group.add_argument("--chroma-key", type=parse_hex_color)
    key_group.add_argument("--auto-key-border", action="store_true")
    parser.add_argument("--border-width", type=int, default=8)
    parser.add_argument("--transparent-threshold", type=float, default=12.0)
    parser.add_argument("--opaque-threshold", type=float, default=96.0)
    parser.add_argument("--no-despill", action="store_true")
    args = parser.parse_args()

    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"input image not found: {input_path}")
    with Image.open(input_path) as image:
        source = image.convert("RGBA")
    key = args.chroma_key
    if args.auto_key_border:
        key = sample_border_key(np.asarray(source.convert("RGB"), dtype=np.float32), args.border_width)
    assert key is not None

    output, report = remove_chroma(
        source,
        key,
        transparent_threshold=args.transparent_threshold,
        opaque_threshold=args.opaque_threshold,
        despill=not args.no_despill,
    )
    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(output_path, format="PNG")
    report.update({"input": str(input_path), "output": str(output_path)})
    if args.json_out:
        write_json(args.json_out, report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
