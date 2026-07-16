#!/usr/bin/env python3
"""Extract transparent game UI assets from known layout-guide slots."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pascal_case(value: str, fallback: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", value)
    if not words:
        return fallback
    return "".join(word[:1].upper() + word[1:] for word in words)


def _find(parent: list[int], label: int) -> int:
    while parent[label] != label:
        parent[label] = parent[parent[label]]
        label = parent[label]
    return label


def _union(parent: list[int], left: int, right: int) -> int:
    left_root = _find(parent, left)
    right_root = _find(parent, right)
    if left_root == right_root:
        return left_root
    if left_root < right_root:
        parent[right_root] = left_root
        return left_root
    parent[left_root] = right_root
    return right_root


def connected_components(mask: np.ndarray, minimum_pixels: int = 1) -> list[dict[str, int]]:
    """Return 8-connected run-length components without OpenCV or SciPy."""
    if mask.ndim != 2:
        raise ValueError("mask must be a 2D array")
    parent: list[int] = []
    all_runs: list[tuple[int, int, int, int]] = []
    previous_runs: list[tuple[int, int, int]] = []

    for y, row in enumerate(mask):
        positions = np.flatnonzero(row)
        current_runs: list[tuple[int, int, int]] = []
        if positions.size:
            split_indices = np.flatnonzero(np.diff(positions) > 1) + 1
            groups = np.split(positions, split_indices)
            previous_cursor = 0
            for group in groups:
                start = int(group[0])
                end = int(group[-1])
                while previous_cursor < len(previous_runs) and previous_runs[previous_cursor][1] < start - 1:
                    previous_cursor += 1
                overlapping: list[int] = []
                cursor = previous_cursor
                while cursor < len(previous_runs) and previous_runs[cursor][0] <= end + 1:
                    overlapping.append(previous_runs[cursor][2])
                    cursor += 1
                if overlapping:
                    label = overlapping[0]
                    for other in overlapping[1:]:
                        label = _union(parent, label, other)
                else:
                    label = len(parent)
                    parent.append(label)
                current_runs.append((start, end, label))
                all_runs.append((y, start, end, label))
        previous_runs = current_runs

    components: dict[int, dict[str, int]] = {}
    for y, start, end, label in all_runs:
        root = _find(parent, label)
        count = end - start + 1
        component = components.setdefault(
            root,
            {"pixels": 0, "left": start, "top": y, "right": end + 1, "bottom": y + 1},
        )
        component["pixels"] += count
        component["left"] = min(component["left"], start)
        component["top"] = min(component["top"], y)
        component["right"] = max(component["right"], end + 1)
        component["bottom"] = max(component["bottom"], y + 1)

    return sorted(
        (component for component in components.values() if component["pixels"] >= minimum_pixels),
        key=lambda component: component["pixels"],
        reverse=True,
    )


def combined_bbox(components: list[dict[str, int]], padding: int, width: int, height: int) -> tuple[int, int, int, int]:
    left = max(0, min(component["left"] for component in components) - padding)
    top = max(0, min(component["top"] for component in components) - padding)
    right = min(width, max(component["right"] for component in components) + padding)
    bottom = min(height, max(component["bottom"] for component in components) + padding)
    return left, top, right, bottom


def touches_boundary(bbox: tuple[int, int, int, int], width: int, height: int, tolerance: int = 1) -> bool:
    left, top, right, bottom = bbox
    return left <= tolerance or top <= tolerance or right >= width - tolerance or bottom >= height - tolerance


def extract_assets(
    source: Image.Image,
    layout: dict[str, Any],
    request: dict[str, Any],
    output_dir: Path,
    alpha_threshold: int = 8,
    minimum_component_pixels: int = 16,
    trim_padding: int = 2,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = source.convert("RGBA")
    slots = layout.get("slots", [])
    assets = request.get("assets", [])
    category = request.get("category")
    if category not in CATEGORY_PREFIX:
        raise ValueError(f"unsupported category: {category}")
    if len(assets) > len(slots):
        raise ValueError(f"request contains {len(assets)} assets but layout has only {len(slots)} slots")

    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    # Treat layout slots as assignment anchors, not hard crop rectangles. Image
    # generation can place an otherwise valid isolated item into the guide's
    # gutter. Cropping the slot rectangle would truncate that item and create a
    # false slot-edge failure. Global components preserve the full silhouette;
    # nearest-center assignment still keeps extraction deterministic and makes
    # touching/merged neighbours fail as an empty assigned slot.
    source_alpha = np.asarray(source.getchannel("A"), dtype=np.uint8)
    global_components = connected_components(source_alpha >= alpha_threshold, minimum_component_pixels)
    assigned_components: list[list[dict[str, int]]] = [[] for _ in slots]
    slot_centers: list[tuple[float, float]] = []
    for slot_data in slots:
        slot_box = slot_data["slot"]
        slot_centers.append(
            (
                (float(slot_box["left"]) + float(slot_box["right"])) / 2.0,
                (float(slot_box["top"]) + float(slot_box["bottom"])) / 2.0,
            )
        )
    for component in global_components:
        component_center = (
            (component["left"] + component["right"]) / 2.0,
            (component["top"] + component["bottom"]) / 2.0,
        )
        nearest_slot = min(
            range(len(slot_centers)),
            key=lambda index: (
                (component_center[0] - slot_centers[index][0]) ** 2
                + (component_center[1] - slot_centers[index][1]) ** 2,
                index,
            ),
        )
        assigned_components[nearest_slot].append(component)

    for visual_index, asset in enumerate(assets, start=1):
        components = assigned_components[visual_index - 1]
        category_index = int(asset.get("category_index", visual_index))
        if category_index <= 0:
            raise ValueError("asset category_index must be positive")

        if not components:
            issues.append({"severity": "fail", "code": "empty-slot", "source_index": visual_index})
            continue

        bbox = combined_bbox(components, trim_padding, source.width, source.height)
        if touches_boundary(bbox, source.width, source.height):
            issues.append(
                {
                    "severity": "fail",
                    "code": "canvas-edge-contact",
                    "source_index": visual_index,
                    "bbox": list(bbox),
                }
            )
        if len(components) > 1:
            issues.append(
                {
                    "severity": "warning",
                    "code": "multiple-components",
                    "source_index": visual_index,
                    "component_count": len(components),
                }
            )

        semantic_name = pascal_case(str(asset.get("semantic_name", "")), f"Asset{visual_index:03d}")
        state = pascal_case(str(asset.get("state", "Default")), "Default")
        filename = (
            f"{CATEGORY_PREFIX[category]}_{category}_{semantic_name}_{state}_{category_index:03d}.png"
        )
        extracted = source.crop(bbox)
        output_path = output_dir / filename
        extracted.save(output_path, format="PNG")
        source_bbox = list(bbox)
        entries.append(
            {
                "id": output_path.stem,
                "category": category,
                "semantic_name": semantic_name,
                "state": state,
                "source_index": visual_index,
                "category_index": category_index,
                "source_bbox": source_bbox,
                "output": output_path.name,
                "width": extracted.width,
                "height": extracted.height,
                "component_count": len(components),
                "foreground_pixels": int(sum(component["pixels"] for component in components)),
                "qa": "warning" if len(components) > 1 else "pass",
            }
        )

    failures = [issue for issue in issues if issue["severity"] == "fail"]
    warnings = [issue for issue in issues if issue["severity"] == "warning"]
    manifest = {
        "schema_version": 1,
        "project_id": request.get("project_id", "game-ui"),
        "category": category,
        "source_image_size": [source.width, source.height],
        "assignment_mode": "global-components-nearest-slot-center",
        "expected_count": len(assets),
        "exported_count": len(entries),
        "assets": entries,
    }
    report = {
        "schema_version": 1,
        "ok": not failures and len(entries) == len(assets),
        "expected_count": len(assets),
        "exported_count": len(entries),
        "pass_count": sum(entry["qa"] == "pass" for entry in entries),
        "warning_count": len(warnings),
        "fail_count": len(failures),
        "issues": issues,
    }
    return manifest, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--layout-json", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest-out", required=True, type=Path)
    parser.add_argument("--qa-out", required=True, type=Path)
    parser.add_argument("--alpha-threshold", type=int, default=8)
    parser.add_argument("--minimum-component-pixels", type=int, default=16)
    parser.add_argument("--trim-padding", type=int, default=2)
    args = parser.parse_args()

    with Image.open(args.input.expanduser().resolve()) as image:
        source = image.convert("RGBA")
    layout = read_json(args.layout_json)
    request = read_json(args.request)
    manifest, report = extract_assets(
        source,
        layout,
        request,
        args.output_dir,
        alpha_threshold=args.alpha_threshold,
        minimum_component_pixels=args.minimum_component_pixels,
        trim_padding=args.trim_padding,
    )
    run_root = args.request.expanduser().resolve().parent
    resolved_input = args.input.expanduser().resolve()
    try:
        manifest["source_sheet"] = resolved_input.relative_to(run_root).as_posix()
    except ValueError:
        manifest["source_sheet"] = resolved_input.name
    write_json(args.manifest_out, manifest)
    write_json(args.qa_out, report)
    print(json.dumps(report, ensure_ascii=False))
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
