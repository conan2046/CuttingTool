#!/usr/bin/env python3
"""Normalize extracted game UI assets to stable transparent canvases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resize_rgba_premultiplied(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize RGBA without letting hidden straight RGB bleed into visible pixels."""
    return image.convert("RGBA").convert("RGBa").resize(size, Image.Resampling.LANCZOS).convert("RGBA")


def suppress_detached_low_alpha_aura(
    image: Image.Image,
    core_alpha_threshold: int = 32,
    keep_radius: int = 2,
) -> tuple[Image.Image, int]:
    """Remove detached low-alpha model glow while preserving edge antialiasing."""
    if not 1 <= core_alpha_threshold <= 255:
        raise ValueError("core_alpha_threshold must be between 1 and 255")
    if keep_radius < 0:
        raise ValueError("keep_radius must be non-negative")

    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    core = alpha.point(lambda value: 255 if value >= core_alpha_threshold else 0)
    if core.getbbox() is None:
        return rgba, 0
    near_core = core if keep_radius == 0 else core.filter(ImageFilter.MaxFilter(keep_radius * 2 + 1))
    cleaned_alpha = Image.composite(alpha, Image.new("L", alpha.size, 0), near_core)
    removed_pixels = sum(alpha.histogram()[1:]) - sum(cleaned_alpha.histogram()[1:])
    rgba.putalpha(cleaned_alpha)
    cleaned = Image.alpha_composite(Image.new("RGBA", rgba.size, (0, 0, 0, 0)), rgba)
    return cleaned, removed_pixels


def normalize_image(
    image: Image.Image,
    target_size: tuple[int, int] | None,
    padding: int,
    alignment: str,
    allow_upscale: bool = False,
    suppress_low_alpha_aura: bool = False,
    aura_core_alpha_threshold: int = 32,
    aura_keep_radius: int = 2,
) -> tuple[Image.Image, dict[str, Any]]:
    image = image.convert("RGBA")
    removed_aura_pixels = 0
    if suppress_low_alpha_aura:
        image, removed_aura_pixels = suppress_detached_low_alpha_aura(
            image,
            core_alpha_threshold=aura_core_alpha_threshold,
            keep_radius=aura_keep_radius,
        )
    alpha_bbox = image.getchannel("A").getbbox()
    if alpha_bbox is None:
        raise ValueError("cannot normalize an empty transparent image")
    trimmed = image.crop(alpha_bbox)

    if target_size is None:
        canvas_width = trimmed.width + 2 * padding
        canvas_height = trimmed.height + 2 * padding
    else:
        canvas_width, canvas_height = target_size
    if canvas_width <= 0 or canvas_height <= 0:
        raise ValueError("target canvas must be positive")
    if padding < 0 or padding * 2 >= canvas_width or padding * 2 >= canvas_height:
        raise ValueError("padding leaves no usable canvas area")
    if alignment not in {"center", "bottom-center"}:
        raise ValueError(f"unsupported alignment: {alignment}")

    available_width = canvas_width - 2 * padding
    available_height = canvas_height - 2 * padding
    scale = min(available_width / trimmed.width, available_height / trimmed.height)
    if not allow_upscale:
        scale = min(1.0, scale)
    resized_width = max(1, round(trimmed.width * scale))
    resized_height = max(1, round(trimmed.height * scale))
    resized = (
        trimmed
        if (resized_width, resized_height) == trimmed.size
        else resize_rgba_premultiplied(trimmed, (resized_width, resized_height))
    )

    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    x = (canvas_width - resized.width) // 2
    if alignment == "bottom-center":
        y = canvas_height - padding - resized.height
    else:
        y = (canvas_height - resized.height) // 2
    canvas.alpha_composite(resized, (x, y))
    return canvas, {
        "source_trim_bbox": list(alpha_bbox),
        "source_trim_size": [trimmed.width, trimmed.height],
        "target_size": [canvas_width, canvas_height],
        "content_size": [resized.width, resized.height],
        "content_position": [x, y],
        "scale": scale,
        "padding": padding,
        "alignment": alignment,
        "upscaled": scale > 1.0,
        "detached_low_alpha_aura_suppressed": suppress_low_alpha_aura,
        "removed_detached_low_alpha_aura_pixels": removed_aura_pixels,
        "aura_core_alpha_threshold": aura_core_alpha_threshold if suppress_low_alpha_aura else None,
        "aura_keep_radius": aura_keep_radius if suppress_low_alpha_aura else None,
    }


def normalize_manifest_assets(
    manifest: dict[str, Any],
    request: dict[str, Any],
    input_dir: Path,
    output_dir: Path,
    allow_upscale: bool = False,
) -> dict[str, Any]:
    input_dir = input_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    requested_target = request.get("target_size")
    target_size = tuple(int(value) for value in requested_target) if requested_target else None
    padding = int(request.get("padding", 8))
    alignment = str(request.get("alignment", "center"))
    suppress_low_alpha_aura = not bool(request.get("allow_attached_glow", False))
    aura_core_alpha_threshold = int(request.get("detached_alpha_aura_threshold", 32))
    aura_keep_radius = int(request.get("detached_alpha_aura_keep_radius", 2))

    normalized_entries: list[dict[str, Any]] = []
    for entry in manifest.get("assets", []):
        source_path = input_dir / entry["output"]
        if not source_path.is_file():
            raise FileNotFoundError(f"extracted asset not found: {source_path}")
        with Image.open(source_path) as image:
            normalized, metadata = normalize_image(
                image,
                target_size=target_size,
                padding=padding,
                alignment=alignment,
                allow_upscale=allow_upscale,
                suppress_low_alpha_aura=suppress_low_alpha_aura,
                aura_core_alpha_threshold=aura_core_alpha_threshold,
                aura_keep_radius=aura_keep_radius,
            )
        output_path = output_dir / source_path.name
        normalized.save(output_path, format="PNG")
        normalized_entry = dict(entry)
        normalized_entry.update(
            {
                "output": output_path.name,
                "width": normalized.width,
                "height": normalized.height,
                "normalization": metadata,
            }
        )
        normalized_entries.append(normalized_entry)

    normalized_manifest = dict(manifest)
    normalized_manifest["stage"] = "normalized"
    normalized_manifest["assets"] = normalized_entries
    normalized_manifest["exported_count"] = len(normalized_entries)
    return normalized_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest-out", required=True, type=Path)
    parser.add_argument("--allow-upscale", action="store_true")
    args = parser.parse_args()

    manifest = read_json(args.manifest)
    request = read_json(args.request)
    normalized_manifest = normalize_manifest_assets(
        manifest,
        request,
        args.input_dir,
        args.output_dir,
        allow_upscale=args.allow_upscale,
    )
    write_json(args.manifest_out, normalized_manifest)
    print(json.dumps({"ok": True, "exported_count": normalized_manifest["exported_count"]}))


if __name__ == "__main__":
    main()
