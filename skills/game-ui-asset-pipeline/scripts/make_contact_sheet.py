#!/usr/bin/env python3
"""Create a labeled checkerboard contact sheet for exported game UI assets."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def checkerboard(size: tuple[int, int], tile: int = 12) -> Image.Image:
    image = Image.new("RGBA", size, "#D9DDE3")
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], tile):
        for x in range(0, size[0], tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle((x, y, min(size[0] - 1, x + tile - 1), min(size[1] - 1, y + tile - 1)), fill="#F3F4F6")
    return image


def make_contact_sheet(
    manifest: dict[str, Any],
    asset_root: Path,
    output: Path,
    columns: int = 4,
    cell_size: int = 192,
    label_height: int = 42,
) -> dict[str, Any]:
    if columns <= 0 or cell_size <= 0 or label_height < 0:
        raise ValueError("columns and cell dimensions must be positive")
    assets = manifest.get("assets", [])
    rows = max(1, math.ceil(len(assets) / columns))
    header_height = 54
    sheet = Image.new("RGBA", (columns * cell_size, header_height + rows * (cell_size + label_height)), "#111827")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    title = f"{manifest.get('project_id', 'game-ui')} | {manifest.get('category', 'Assets')} | count={len(assets)}"
    draw.text((12, 12), title, fill="#FFFFFF", font=font)
    draw.text((12, 31), "Checkerboard is QA preview only; exported assets remain transparent PNG.", fill="#CBD5E1", font=font)

    missing: list[str] = []
    for index, entry in enumerate(assets):
        column = index % columns
        row = index // columns
        x = column * cell_size
        y = header_height + row * (cell_size + label_height)
        preview = checkerboard((cell_size, cell_size))
        asset_path = asset_root / entry["output"]
        if asset_path.is_file():
            with Image.open(asset_path) as image:
                asset = image.convert("RGBA")
            scale = min((cell_size - 16) / asset.width, (cell_size - 16) / asset.height, 1.0)
            target = (max(1, round(asset.width * scale)), max(1, round(asset.height * scale)))
            if target != asset.size:
                asset = asset.resize(target, Image.Resampling.LANCZOS)
            preview.alpha_composite(asset, ((cell_size - asset.width) // 2, (cell_size - asset.height) // 2))
        else:
            missing.append(str(asset_path))
            ImageDraw.Draw(preview).line((16, 16, cell_size - 16, cell_size - 16), fill="#DC2626", width=6)
            ImageDraw.Draw(preview).line((cell_size - 16, 16, 16, cell_size - 16), fill="#DC2626", width=6)
        sheet.alpha_composite(preview, (x, y))
        draw.rectangle((x, y, x + cell_size - 1, y + cell_size - 1), outline="#475569", width=1)
        label = str(entry.get("id", entry.get("output", f"asset-{index + 1}")))
        if len(label) > 30:
            label = label[:27] + "..."
        draw.text((x + 6, y + cell_size + 6), label, fill="#FFFFFF", font=font)
        draw.text((x + 6, y + cell_size + 22), f"qa={entry.get('qa', 'unknown')}", fill="#CBD5E1", font=font)

    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(output, format="PNG")
    return {"ok": not missing, "output": str(output), "asset_count": len(assets), "missing": missing}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--asset-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--cell-size", type=int, default=192)
    args = parser.parse_args()
    report = make_contact_sheet(
        read_json(args.manifest),
        args.asset_root.expanduser().resolve(),
        args.output,
        columns=args.columns,
        cell_size=args.cell_size,
    )
    print(json.dumps(report, ensure_ascii=False))
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
