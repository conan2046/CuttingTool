#!/usr/bin/env python3
"""Render deterministic multi-size previews for Panel/Button nine-slice assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from infer_nine_slice import infer_nine_slice
from normalize_assets import resize_rgba_premultiplied


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def nine_slice_resize(image: Image.Image, target: tuple[int, int], border: list[int]) -> Image.Image:
    source = image.convert("RGBA")
    left, bottom, right, top = [int(value) for value in border]
    target_width = max(int(target[0]), left + right + 1)
    target_height = max(int(target[1]), top + bottom + 1)
    source_x = [0, left, source.width - right, source.width]
    source_y = [0, top, source.height - bottom, source.height]
    target_x = [0, left, target_width - right, target_width]
    target_y = [0, top, target_height - bottom, target_height]
    result = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
    for row in range(3):
        for column in range(3):
            patch = source.crop((source_x[column], source_y[row], source_x[column + 1], source_y[row + 1]))
            size = (target_x[column + 1] - target_x[column], target_y[row + 1] - target_y[row])
            if patch.size != size:
                patch = resize_rgba_premultiplied(patch, size)
            result.alpha_composite(patch, (target_x[column], target_y[row]))
    return result


def checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
    background = Image.new("RGBA", size, (232, 232, 232, 255))
    draw = ImageDraw.Draw(background)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, min(size[0], x + cell), min(size[1], y + cell)), fill=(196, 196, 196, 255))
    return background


def make_preview(manifest: dict[str, Any], asset_root: Path, output: Path) -> dict[str, Any]:
    scales = (0.5, 1.5, 2.0)
    rows: list[tuple[str, Image.Image, list[tuple[str, Image.Image]], dict[str, Any]]] = []
    issues: list[dict[str, Any]] = []
    for entry in manifest.get("assets", []):
        if entry.get("category") not in {"Panel", "Button"}:
            continue
        path = asset_root / str(entry["output"])
        with Image.open(path) as opened:
            source = opened.convert("RGBA")
        inferred = infer_nine_slice(source)
        if not inferred.get("apply"):
            issues.append({"file": str(entry["output"]), "code": "nine-slice-preview-border-unavailable", "details": inferred})
            continue
        variants = [(f"{scale:g}x", nine_slice_resize(source, (round(source.width * scale), round(source.height * scale)), inferred["border"])) for scale in scales]
        rows.append((str(entry["id"]), source, variants, inferred))
    if not rows:
        return {"ok": False, "issues": issues or [{"code": "no-nine-slice-assets"}], "assets": []}

    cell_width, cell_height, label_height, gap = 420, 220, 24, 16
    canvas = Image.new("RGBA", (gap + 4 * (cell_width + gap), gap + len(rows) * (cell_height + label_height + gap)), (34, 38, 48, 255))
    draw = ImageDraw.Draw(canvas)
    report_assets: list[dict[str, Any]] = []
    for row_index, (asset_id, source, variants, inferred) in enumerate(rows):
        items = [("original", source), *variants]
        y = gap + row_index * (cell_height + label_height + gap)
        for column, (label, item) in enumerate(items):
            x = gap + column * (cell_width + gap)
            fitted = item.copy()
            fitted.thumbnail((cell_width - 16, cell_height - 16), Image.Resampling.LANCZOS)
            tile = checker((cell_width, cell_height))
            tile.alpha_composite(fitted, ((cell_width - fitted.width) // 2, (cell_height - fitted.height) // 2))
            canvas.alpha_composite(tile, (x, y + label_height))
            draw.text((x + 4, y + 4), f"{asset_id} | {label} | {item.width}x{item.height}", fill=(245, 245, 245, 255))
        report_assets.append({"id": asset_id, "border": inferred["border"], "confidence": inferred["confidence"], "sizes": [[item.width, item.height] for _, item in variants]})
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output)
    return {"ok": not issues, "output": str(output), "assets": report_assets, "issues": issues}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--asset-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    args = parser.parse_args()
    report = make_preview(read_json(args.manifest), args.asset_root.expanduser().resolve(), args.output.expanduser().resolve())
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
