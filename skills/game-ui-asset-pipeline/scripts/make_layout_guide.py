#!/usr/bin/env python3
"""Create a deterministic layout guide for a game UI production sheet."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class Box:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass(frozen=True)
class LayoutSpec:
    width: int
    height: int
    columns: int
    rows: int
    outer_margin: int = 96
    gutter: int = 48
    safe_padding: int = 64

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        if self.columns <= 0 or self.rows <= 0:
            raise ValueError("columns and rows must be positive")

        usable_width = self.width - 2 * self.outer_margin - (self.columns - 1) * self.gutter
        usable_height = self.height - 2 * self.outer_margin - (self.rows - 1) * self.gutter
        if usable_width < self.columns or usable_height < self.rows:
            raise ValueError("margins and gutters leave no usable slot area")

        minimum_slot_width = usable_width // self.columns
        minimum_slot_height = usable_height // self.rows
        if self.safe_padding * 2 >= minimum_slot_width:
            raise ValueError("safe_padding leaves no horizontal safe area")
        if self.safe_padding * 2 >= minimum_slot_height:
            raise ValueError("safe_padding leaves no vertical safe area")


def _partition(total: int, count: int) -> list[int]:
    base, remainder = divmod(total, count)
    return [base + (1 if index < remainder else 0) for index in range(count)]


def calculate_slots(spec: LayoutSpec) -> list[dict[str, Any]]:
    spec.validate()
    usable_width = spec.width - 2 * spec.outer_margin - (spec.columns - 1) * spec.gutter
    usable_height = spec.height - 2 * spec.outer_margin - (spec.rows - 1) * spec.gutter
    widths = _partition(usable_width, spec.columns)
    heights = _partition(usable_height, spec.rows)

    slots: list[dict[str, Any]] = []
    top = spec.outer_margin
    visual_index = 1
    for row_index, slot_height in enumerate(heights):
        left = spec.outer_margin
        for column_index, slot_width in enumerate(widths):
            slot = Box(left, top, left + slot_width, top + slot_height)
            safe = Box(
                slot.left + spec.safe_padding,
                slot.top + spec.safe_padding,
                slot.right - spec.safe_padding,
                slot.bottom - spec.safe_padding,
            )
            slots.append(
                {
                    "index": visual_index,
                    "row": row_index,
                    "column": column_index,
                    "slot": asdict(slot),
                    "safe_box": asdict(safe),
                    "center": [(safe.left + safe.right) // 2, (safe.top + safe.bottom) // 2],
                }
            )
            visual_index += 1
            left = slot.right + spec.gutter
        top += slot_height + spec.gutter
    return slots


def render_layout_guide(spec: LayoutSpec, output: Path, title: str = "UI Asset Layout Guide") -> dict[str, Any]:
    slots = calculate_slots(spec)
    image = Image.new("RGB", (spec.width, spec.height), "#F4F6F8")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    draw.rectangle((0, 0, spec.width - 1, spec.height - 1), outline="#2F3B4A", width=4)
    draw.text((16, 14), title, fill="#111827", font=font)
    draw.text(
        (16, 34),
        f"{spec.columns}x{spec.rows} | slots={len(slots)} | layout reference only",
        fill="#4B5563",
        font=font,
    )

    for slot_data in slots:
        slot = Box(**slot_data["slot"])
        safe = Box(**slot_data["safe_box"])
        center_x, center_y = slot_data["center"]
        draw.rectangle((slot.left, slot.top, slot.right - 1, slot.bottom - 1), outline="#2563EB", width=4)
        draw.rectangle((safe.left, safe.top, safe.right - 1, safe.bottom - 1), outline="#F59E0B", width=3)
        draw.line((center_x - 14, center_y, center_x + 14, center_y), fill="#DC2626", width=2)
        draw.line((center_x, center_y - 14, center_x, center_y + 14), fill="#DC2626", width=2)
        draw.text((slot.left + 10, slot.top + 8), str(slot_data["index"]), fill="#111827", font=font)

    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG")
    return {
        "schema_version": 1,
        "purpose": "layout-reference-only",
        "warning": "Do not copy visible guide lines, labels, colors, or center marks into generated art.",
        "image": str(output),
        "layout": asdict(spec),
        "slots": slots,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--width", type=int, default=2048)
    parser.add_argument("--height", type=int, default=2048)
    parser.add_argument("--columns", type=int, required=True)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--outer-margin", type=int, default=96)
    parser.add_argument("--gutter", type=int, default=48)
    parser.add_argument("--safe-padding", type=int, default=64)
    parser.add_argument("--title", default="UI Asset Layout Guide")
    args = parser.parse_args()

    spec = LayoutSpec(
        width=args.width,
        height=args.height,
        columns=args.columns,
        rows=args.rows,
        outer_margin=args.outer_margin,
        gutter=args.gutter,
        safe_padding=args.safe_padding,
    )
    payload = render_layout_guide(spec, args.output, args.title)
    if args.json_out:
        write_json(args.json_out, payload)
    print(json.dumps({"ok": True, "output": str(args.output.resolve()), "slots": len(payload["slots"])}))


if __name__ == "__main__":
    main()
