#!/usr/bin/env python3
"""Diagnose an unknown UI sheet and emit candidate bboxes plus a correction template."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from extract_sheet_assets import CATEGORY_PREFIX, connected_components
from prepare_ui_run import CATEGORY_DEFAULTS
from remove_chroma_key import format_hex, recommend_chroma_thresholds


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dominant_colors(rgb: np.ndarray, limit: int = 2) -> list[tuple[int, int, int]]:
    sample = rgb[:: max(1, rgb.shape[0] // 512), :: max(1, rgb.shape[1] // 512)]
    quantized = (sample.astype(np.uint16) // 8 * 8).astype(np.uint8).reshape(-1, 3)
    packed = (
        quantized[:, 0].astype(np.uint32) << 16
        | quantized[:, 1].astype(np.uint32) << 8
        | quantized[:, 2].astype(np.uint32)
    )
    values, counts = np.unique(packed, return_counts=True)
    order = np.argsort(counts)[::-1][:limit]
    return [
        (int((values[index] >> 16) & 255), int((values[index] >> 8) & 255), int(values[index] & 255))
        for index in order
    ]


def _run_lengths(values: np.ndarray, valid: np.ndarray) -> list[int]:
    lengths: list[int] = []
    start = 0
    while start < len(values):
        if not valid[start]:
            start += 1
            continue
        end = start + 1
        while end < len(values) and valid[end] and values[end] == values[start]:
            end += 1
        lengths.append(end - start)
        start = end
    return lengths[1:-1] if len(lengths) > 2 else lengths


def detect_checkerboard(rgb: np.ndarray, color_threshold: float = 18.0) -> dict[str, Any] | None:
    colors = dominant_colors(rgb, 2)
    if len(colors) < 2:
        return None
    first = np.asarray(colors[0], dtype=np.float32)
    second = np.asarray(colors[1], dtype=np.float32)
    if float(np.linalg.norm(first - second)) < 12.0:
        return None
    distance_first = np.linalg.norm(rgb.astype(np.float32) - first.reshape(1, 1, 3), axis=2)
    distance_second = np.linalg.norm(rgb.astype(np.float32) - second.reshape(1, 1, 3), axis=2)
    nearest = np.minimum(distance_first, distance_second)
    background = nearest <= color_threshold
    coverage = float(np.mean(background))
    if coverage < 0.45:
        return None
    labels = distance_second < distance_first
    candidate_lengths: list[int] = []
    edge = min(8, rgb.shape[0], rgb.shape[1])
    for y in list(range(edge)) + list(range(max(edge, rgb.shape[0] - edge), rgb.shape[0])):
        candidate_lengths.extend(_run_lengths(labels[y], background[y]))
    for x in list(range(edge)) + list(range(max(edge, rgb.shape[1] - edge), rgb.shape[1])):
        candidate_lengths.extend(_run_lengths(labels[:, x], background[:, x]))
    candidate_lengths = [value for value in candidate_lengths if 2 <= value <= min(rgb.shape[:2]) // 2]
    if not candidate_lengths:
        return None
    tile = int(round(float(np.median(candidate_lengths))))
    if tile < 2:
        return None

    scores: list[float] = []
    if rgb.shape[1] > tile:
        valid = background[:, :-tile] & background[:, tile:]
        if np.any(valid):
            scores.append(float(np.mean(labels[:, :-tile][valid] != labels[:, tile:][valid])))
    if rgb.shape[0] > tile:
        valid = background[:-tile, :] & background[tile:, :]
        if np.any(valid):
            scores.append(float(np.mean(labels[:-tile, :][valid] != labels[tile:, :][valid])))
    if rgb.shape[1] > tile * 2:
        valid = background[:, :-tile * 2] & background[:, tile * 2 :]
        if np.any(valid):
            scores.append(float(np.mean(labels[:, :-tile * 2][valid] == labels[:, tile * 2 :][valid])))
    if rgb.shape[0] > tile * 2:
        valid = background[:-tile * 2, :] & background[tile * 2 :, :]
        if np.any(valid):
            scores.append(float(np.mean(labels[:-tile * 2, :][valid] == labels[tile * 2 :, :][valid])))
    score = float(np.mean(scores)) if scores else 0.0
    if score < 0.82:
        return None
    return {
        "colors": [format_hex(colors[0]), format_hex(colors[1])],
        "tile_size": tile,
        "coverage": round(coverage, 6),
        "pattern_score": round(score, 6),
        "background_mask": background,
    }


def border_color(rgb: np.ndarray, border_width: int = 8) -> tuple[int, int, int]:
    width = max(1, min(border_width, min(rgb.shape[0], rgb.shape[1]) // 4))
    samples = np.concatenate(
        (
            rgb[:width].reshape(-1, 3),
            rgb[-width:].reshape(-1, 3),
            rgb[:, :width].reshape(-1, 3),
            rgb[:, -width:].reshape(-1, 3),
        ),
        axis=0,
    )
    return tuple(int(round(value)) for value in np.median(samples, axis=0))


def padded_bbox(component: dict[str, int], padding: int, width: int, height: int) -> list[int]:
    return [
        max(0, component["left"] - padding),
        max(0, component["top"] - padding),
        min(width, component["right"] + padding),
        min(height, component["bottom"] + padding),
    ]


def row_major(components: list[dict[str, int]]) -> list[dict[str, int]]:
    if not components:
        return []
    median_height = max(1.0, float(np.median([item["bottom"] - item["top"] for item in components])))
    return sorted(
        components,
        key=lambda item: (
            round(((item["top"] + item["bottom"]) / 2.0) / median_height),
            item["left"],
            item["top"],
        ),
    )


def render_overlay(source: Image.Image, assets: list[dict[str, Any]], output: Path, status: str) -> None:
    preview = source.convert("RGB")
    draw = ImageDraw.Draw(preview)
    font = ImageFont.load_default()
    for asset in assets:
        left, top, right, bottom = asset["bbox"]
        color = "#22C55E" if asset["enabled"] else "#EF4444"
        draw.rectangle((left, top, max(left, right - 1), max(top, bottom - 1)), outline=color, width=3)
        label = f"{asset['source_index']:03d} {asset['semantic_name']}"
        text_box = draw.textbbox((left, top), label, font=font)
        label_height = text_box[3] - text_box[1] + 4
        draw.rectangle((left, max(0, top - label_height), left + text_box[2] - text_box[0] + 4, top), fill="#111827")
        draw.text((left + 2, max(0, top - label_height + 2)), label, fill="#FFFFFF", font=font)
    draw.rectangle((0, 0, preview.width - 1, 24), fill="#111827")
    draw.text((8, 7), f"diagnosis={status} candidates={len(assets)}", fill="#FFFFFF", font=font)
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    preview.save(output, format="PNG")


def diagnose_sheet(
    source: Image.Image,
    source_name: str,
    category: str,
    minimum_component_pixels: int = 64,
    bbox_padding: int = 4,
    background_threshold: float = 24.0,
) -> tuple[dict[str, Any], dict[str, Any], Image.Image]:
    if category not in CATEGORY_PREFIX:
        raise ValueError(f"unsupported category: {category}")
    rgba = source.convert("RGBA")
    array = np.asarray(rgba, dtype=np.uint8)
    rgb = array[:, :, :3]
    alpha = array[:, :, 3]
    issues: list[dict[str, Any]] = []
    checker = None
    background: dict[str, Any]
    if int(alpha.min()) < 255:
        classification = "alpha-sheet"
        foreground = alpha >= 8
        background = {"mode": "alpha", "export_supported": True}
    else:
        checker = detect_checkerboard(rgb)
        if checker is not None:
            classification = "checkerboard-presentation"
            foreground = ~checker.pop("background_mask")
            background = {"mode": "checkerboard", "export_supported": False, **checker}
            issues.append(
                {
                    "severity": "fail",
                    "code": "fake-checkerboard-background",
                    "message": "Checkerboard pixels are baked into RGB and cannot be treated as real transparency.",
                }
            )
        else:
            key = border_color(rgb)
            distance = np.linalg.norm(rgb.astype(np.float32) - np.asarray(key, dtype=np.float32), axis=2)
            border = np.concatenate((distance[0], distance[-1], distance[:, 0], distance[:, -1]))
            background_coverage = float(np.mean(distance <= background_threshold))
            border_coverage = float(np.mean(border <= background_threshold))
            foreground = distance > background_threshold
            if border_coverage >= 0.85 and background_coverage >= 0.20:
                classification = "flat-background-sheet"
                threshold_diagnostics = recommend_chroma_thresholds(rgba, key)
                export_supported = bool(threshold_diagnostics["auto_apply"])
                background = {
                    "mode": "flat-color",
                    "export_supported": export_supported,
                    "color": format_hex(key),
                    "threshold": background_threshold,
                    "transparent_threshold": threshold_diagnostics["suggested_transparent_threshold"],
                    "opaque_threshold": threshold_diagnostics["suggested_opaque_threshold"],
                    "coverage": round(background_coverage, 6),
                    "border_coverage": round(border_coverage, 6),
                    "threshold_diagnostics": threshold_diagnostics,
                }
                issues.extend(threshold_diagnostics["issues"])
            else:
                classification = "opaque-mixed-image"
                background = {
                    "mode": "unresolved",
                    "export_supported": False,
                    "sampled_border_color": format_hex(key),
                    "coverage": round(background_coverage, 6),
                    "border_coverage": round(border_coverage, 6),
                }
                issues.append(
                    {
                        "severity": "fail",
                        "code": "unresolved-opaque-background",
                        "message": "No reliable Alpha, flat background, or checkerboard pattern was found.",
                    }
                )

    components = row_major(connected_components(foreground, minimum_component_pixels))
    assets: list[dict[str, Any]] = []
    for index, component in enumerate(components, start=1):
        bbox = padded_bbox(component, bbox_padding, rgba.width, rgba.height)
        touches_canvas = bbox[0] == 0 or bbox[1] == 0 or bbox[2] == rgba.width or bbox[3] == rgba.height
        if touches_canvas:
            issues.append({"severity": "warning", "code": "candidate-touches-canvas", "source_index": index, "bbox": bbox})
        assets.append(
            {
                "source_index": index,
                "enabled": True,
                "bbox": bbox,
                "semantic_name": f"Asset{index:03d}",
                "category": category,
                "state": "Default",
                "category_index": index,
                "notes": "",
            }
        )
    if not assets:
        issues.append({"severity": "fail", "code": "no-candidates", "message": "No extractable candidate was detected."})

    failures = [issue for issue in issues if issue["severity"] == "fail"]
    warnings = [issue for issue in issues if issue["severity"] == "warning"]
    status = "ready-for-review" if not failures else "manual-review-required"
    diagnosis = {
        "schema_version": 1,
        "status": status,
        "classification": classification,
        "source_image": source_name,
        "image_size": [rgba.width, rgba.height],
        "background": background,
        "candidate_count": len(assets),
        "warning_count": len(warnings),
        "fail_count": len(failures),
        "issues": issues,
    }
    corrections = {
        "schema_version": 1,
        "approved": False,
        "source_image": source_name,
        "image_size": [rgba.width, rgba.height],
        "classification": classification,
        "background": background,
        "normalization": {
            "target_size": CATEGORY_DEFAULTS[category]["target_size"],
            "padding": 8,
            "alignment": CATEGORY_DEFAULTS[category]["alignment"],
            "allow_upscale": False,
        },
        "assets": assets,
    }
    return diagnosis, corrections, rgba


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--category", required=True, choices=sorted(CATEGORY_PREFIX))
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument("--corrections-out", required=True, type=Path)
    parser.add_argument("--preview-out", required=True, type=Path)
    parser.add_argument("--minimum-component-pixels", type=int, default=64)
    parser.add_argument("--bbox-padding", type=int, default=4)
    parser.add_argument("--background-threshold", type=float, default=24.0)
    args = parser.parse_args()
    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"input image not found: {input_path}")
    with Image.open(input_path) as image:
        source = image.convert("RGBA")
    diagnosis, corrections, _ = diagnose_sheet(
        source,
        input_path.name,
        args.category,
        minimum_component_pixels=args.minimum_component_pixels,
        bbox_padding=args.bbox_padding,
        background_threshold=args.background_threshold,
    )
    write_json(args.json_out, diagnosis)
    write_json(args.corrections_out, corrections)
    render_overlay(source, corrections["assets"], args.preview_out, diagnosis["status"])
    print(json.dumps(diagnosis, ensure_ascii=False))
    if diagnosis["status"] == "manual-review-required":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
