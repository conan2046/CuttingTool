#!/usr/bin/env python3
"""Prepare a game UI asset run with prompts, layout guides, and a job manifest."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from make_layout_guide import LayoutSpec, render_layout_guide, write_json


CATEGORY_DEFAULTS: dict[str, dict[str, Any]] = {
    "Panel": {"canvas": [2048, 2048], "grid": [2, 2], "target_size": None, "alignment": "center"},
    "Button": {"canvas": [2048, 2048], "grid": [3, 4], "target_size": None, "alignment": "center"},
    "Icon_Nav": {"canvas": [2048, 2048], "grid": [4, 4], "target_size": [128, 128], "alignment": "center"},
    "Icon_Status": {"canvas": [2048, 2048], "grid": [4, 4], "target_size": [128, 128], "alignment": "center"},
    "Icon_General": {"canvas": [2048, 2048], "grid": [4, 4], "target_size": [128, 128], "alignment": "center"},
    "Icon_Item": {"canvas": [2048, 2048], "grid": [4, 4], "target_size": [128, 128], "alignment": "center"},
    "Icon_Equip": {"canvas": [2048, 2048], "grid": [4, 4], "target_size": [128, 128], "alignment": "center"},
    "Icon_Skill": {"canvas": [2048, 2048], "grid": [4, 4], "target_size": [128, 128], "alignment": "center"},
    "Icon_Effect": {"canvas": [2048, 2048], "grid": [4, 3], "target_size": [256, 256], "alignment": "center"},
}

CATEGORY_PREFIX = {
    "Panel": "01",
    "Button": "02",
    "Icon_Nav": "03",
    "Icon_Status": "04",
    "Icon_General": "05",
    "Icon_Item": "06",
    "Icon_Equip": "07",
    "Icon_Skill": "08",
    "Icon_Effect": "09",
}


@dataclass(frozen=True)
class AssetRequest:
    semantic_name: str
    state: str = "Default"
    description: str = ""


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-_").lower()
    return value or "game-ui"


def parse_pair(value: str, label: str) -> list[int]:
    match = re.fullmatch(r"\s*(\d+)\s*[xX×]\s*(\d+)\s*", value)
    if not match:
        raise argparse.ArgumentTypeError(f"{label} must use WIDTHxHEIGHT format")
    return [int(match.group(1)), int(match.group(2))]


def parse_asset(value: str) -> AssetRequest:
    parts = [part.strip() for part in value.split("|", 2)]
    semantic_name = parts[0]
    if not semantic_name:
        raise argparse.ArgumentTypeError("asset semantic name cannot be empty")
    state = parts[1] if len(parts) > 1 and parts[1] else "Default"
    description = parts[2] if len(parts) > 2 else ""
    return AssetRequest(semantic_name=semantic_name, state=state, description=description)


def normalize_chroma_key(value: str, subject_uses_green: bool) -> str:
    if value.lower() == "auto":
        return "#FF00FF" if subject_uses_green else "#00FF00"
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError("chroma key must be auto or #RRGGBB")
    return value.upper()


def copy_reference(source: Path, destination_dir: Path, prefix: str) -> Path:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"reference image not found: {source}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{prefix}-{source.name}"
    shutil.copy2(source, destination)
    return destination


def build_prompt(
    category: str,
    assets: list[AssetRequest],
    width: int,
    height: int,
    columns: int,
    rows: int,
    chroma_key: str,
    style_notes: str,
    allow_attached_glow: bool,
) -> str:
    ordered_assets = "\n".join(
        f"{index}. {asset.semantic_name} | state={asset.state}"
        + (f" | {asset.description}" if asset.description else "")
        for index, asset in enumerate(assets, start=1)
    )
    effect_rule = (
        "Small hard-edged glow may be kept only when it touches the main subject and remains inside the safe box."
        if allow_attached_glow
        else "Do not add glow, aura, detached particles, floating effects, or shadows."
    )
    style_line = style_notes.strip() or "Follow the attached canonical UI style reference exactly."
    return f"""Task: generate a production-ready game UI `{category}` asset sheet for automatic extraction.

Input image roles:
- Canonical UI Style Reference: use only to lock style, materials, palette, outlines, lighting, viewing angle, and polish.
- Layout Guide: use only for slot count, spacing, centering, and safe padding. Do not copy any visible guide line, label, color, box, or center mark.

Ordered assets, left-to-right and top-to-bottom:
{ordered_assets}

Layout contract:
- Canvas: {width}x{height}
- Grid: {columns} columns x {rows} rows
- Exact asset count: {len(assets)}
- One complete centered asset in each invisible slot
- Keep assets mutually separated by a large area of pure background
- No overlap, touching, clipping, cross-slot content, extra assets, or empty slots before the final requested asset
- Keep all outlines, corners, and allowed attached effects inside each safe box

Style:
{style_line}
- Preserve one coherent UI family across every asset
- Keep details readable at mobile-game UI size

Background contract:
- Perfectly flat pure {chroma_key} chroma-key background
- No gradient, texture, lighting variation, noise, reflection, floor, contact shadow, or cast shadow
- Do not use {chroma_key} or visually similar colors inside any asset, outline, highlight, shadow, or effect

Forbidden:
- Text, numbers, labels, frame indices, logos, watermarks
- Checkerboard transparency, visible grids, separators, guide marks, or slot borders
- Scenery, environment, floor, reflections, presentation cards, or decorations between assets
- Cropped assets, merged assets, duplicated assets, or unrequested variants
- {effect_rule}

Before returning, reject the result unless the exact requested count, order, separation, complete silhouettes, flat chroma background, and canonical style are all correct.
"""


def create_run(args: argparse.Namespace) -> Path:
    project_id = slugify(args.project_id)
    category = args.category
    defaults = CATEGORY_DEFAULTS[category]
    assets: list[AssetRequest] = args.asset

    canvas = parse_pair(args.canvas, "canvas") if args.canvas else defaults["canvas"]
    grid = parse_pair(args.grid, "grid") if args.grid else defaults["grid"]
    target_size = parse_pair(args.target_size, "target-size") if args.target_size else defaults["target_size"]
    width, height = canvas
    columns, rows = grid
    if len(assets) > columns * rows:
        raise ValueError(f"asset count {len(assets)} exceeds grid capacity {columns * rows}")

    chroma_key = normalize_chroma_key(args.chroma_key, args.subject_uses_green)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else (Path.cwd() / "output" / f"{project_id}-{timestamp}").resolve()
    )
    if run_dir.exists() and any(run_dir.iterdir()) and not args.force:
        raise FileExistsError(f"output directory is not empty: {run_dir}; use --force to reuse it")

    directories = [
        run_dir / "references" / "layout-guides",
        run_dir / "prompts",
        run_dir / "generated",
        run_dir / "extracted",
        run_dir / "normalized",
        run_dir / "final" / category,
        run_dir / "qa",
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    reference_records: list[dict[str, str]] = []
    if args.canonical_style:
        copied = copy_reference(args.canonical_style, run_dir / "references", "canonical")
        reference_records.append({"path": str(copied.relative_to(run_dir)).replace("\\", "/"), "role": "canonical-ui-style"})
    for index, reference in enumerate(args.reference, start=1):
        copied = copy_reference(reference, run_dir / "references", f"reference-{index:02d}")
        reference_records.append({"path": str(copied.relative_to(run_dir)).replace("\\", "/"), "role": "supporting-style-reference"})

    layout_spec = LayoutSpec(
        width=width,
        height=height,
        columns=columns,
        rows=rows,
        outer_margin=args.outer_margin,
        gutter=args.gutter,
        safe_padding=args.safe_padding,
    )
    sheet_slug = category.lower().replace("_", "-")
    guide_path = run_dir / "references" / "layout-guides" / f"{sheet_slug}-sheet-01.png"
    guide_json = run_dir / "references" / "layout-guides" / f"{sheet_slug}-sheet-01.json"
    guide_payload = render_layout_guide(layout_spec, guide_path, f"{category} Sheet Layout")
    write_json(guide_json, guide_payload)

    prompt = build_prompt(
        category=category,
        assets=assets,
        width=width,
        height=height,
        columns=columns,
        rows=rows,
        chroma_key=chroma_key,
        style_notes=args.style_notes,
        allow_attached_glow=args.allow_attached_glow,
    )
    prompt_path = run_dir / "prompts" / f"{sheet_slug}-sheet-01.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    request_payload = {
        "schema_version": 2,
        "project_id": project_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "style_notes": args.style_notes,
        "chroma_key": chroma_key,
        "canvas": canvas,
        "grid": grid,
        "target_size": target_size,
        "alignment": args.alignment or defaults["alignment"],
        "padding": args.padding,
        "allow_attached_glow": args.allow_attached_glow,
        "assets": [asdict(asset) for asset in assets],
        "expected_count": len(assets),
        "references": reference_records,
    }
    write_json(run_dir / "request.json", request_payload)

    output_name = f"{sheet_slug}-sheet-01.png"
    job_payload = {
        "schema_version": 2,
        "created_at": request_payload["created_at"],
        "jobs": [
            {
                "id": f"{sheet_slug}-sheet-01",
                "kind": "production-asset-sheet",
                "category": category,
                "status": "ready",
                "expected_count": len(assets),
                "prompt_file": str(prompt_path.relative_to(run_dir)).replace("\\", "/"),
                "layout_guide": str(guide_path.relative_to(run_dir)).replace("\\", "/"),
                "layout_json": str(guide_json.relative_to(run_dir)).replace("\\", "/"),
                "input_images": reference_records
                + [{"path": str(guide_path.relative_to(run_dir)).replace("\\", "/"), "role": "layout-guide-only"}],
                "generated_output": f"generated/{output_name}",
                "final_directory": f"final/{category}",
            }
        ],
    }
    write_json(run_dir / "jobs.json", job_payload)
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--category", required=True, choices=sorted(CATEGORY_DEFAULTS))
    parser.add_argument(
        "--asset",
        required=True,
        action="append",
        type=parse_asset,
        help="SemanticName|State|optional description; repeat for each asset in visual order",
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--canonical-style", type=Path)
    parser.add_argument("--reference", type=Path, action="append", default=[])
    parser.add_argument("--style-notes", default="")
    parser.add_argument("--canvas", help="WIDTHxHEIGHT; category default when omitted")
    parser.add_argument("--grid", help="COLUMNSxROWS; category default when omitted")
    parser.add_argument("--target-size", help="WIDTHxHEIGHT; category default when omitted")
    parser.add_argument("--chroma-key", default="auto")
    parser.add_argument("--subject-uses-green", action="store_true")
    parser.add_argument("--allow-attached-glow", action="store_true")
    parser.add_argument("--outer-margin", type=int, default=96)
    parser.add_argument("--gutter", type=int, default=48)
    parser.add_argument("--safe-padding", type=int, default=64)
    parser.add_argument("--padding", type=int, default=8)
    parser.add_argument("--alignment", choices=["center", "bottom-center"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    run_dir = create_run(args)
    print(json.dumps({"ok": True, "run_dir": str(run_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
