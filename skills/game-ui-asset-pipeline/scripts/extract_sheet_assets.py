#!/usr/bin/env python3
"""Extract transparent game UI assets from known layout-guide slots."""

from __future__ import annotations

import argparse
import json
import math
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


FRAGMENT_POLICY_DEFAULTS: dict[str, dict[str, float | int | str]] = {
    "Panel": {"merge_distance": 12.0, "merge_distance_ratio": 0.06, "merge_distance_max": 64.0},
    "Button": {"merge_distance": 12.0, "merge_distance_ratio": 0.06, "merge_distance_max": 48.0},
    "Icon_Nav": {"merge_distance": 12.0, "merge_distance_ratio": 0.12, "merge_distance_max": 48.0},
    "Icon_Status": {"merge_distance": 12.0, "merge_distance_ratio": 0.12, "merge_distance_max": 48.0},
    "Icon_General": {"merge_distance": 12.0, "merge_distance_ratio": 0.12, "merge_distance_max": 48.0},
    "Icon_Item": {"merge_distance": 12.0, "merge_distance_ratio": 0.12, "merge_distance_max": 48.0},
    "Icon_Equip": {"merge_distance": 12.0, "merge_distance_ratio": 0.12, "merge_distance_max": 48.0},
    "Icon_Skill": {"merge_distance": 12.0, "merge_distance_ratio": 0.15, "merge_distance_max": 96.0},
    "Icon_Effect": {"merge_distance": 12.0, "merge_distance_ratio": 0.18, "merge_distance_max": 128.0},
}


def resolve_fragment_policy(
    category: str,
    request_policy: Any = None,
    merge_distance: float | None = None,
    merge_distance_ratio: float | None = None,
    merge_distance_max: float | None = None,
    major_component_ratio: float | None = None,
) -> dict[str, float | int | str]:
    policy = {
        **FRAGMENT_POLICY_DEFAULTS[category],
        "major_component_ratio": 0.35,
        "detached_action": "warning",
        "small_detached_max_pixels": 0,
        "small_detached_max_anchor_ratio": 0.0,
    }
    if request_policy is not None:
        if not isinstance(request_policy, dict):
            raise ValueError("fragment_policy must be an object")
        unknown = set(request_policy) - set(policy)
        if unknown:
            raise ValueError("unsupported fragment_policy fields: " + ", ".join(sorted(unknown)))
        policy.update(request_policy)
    direct_overrides = {
        "merge_distance": merge_distance,
        "merge_distance_ratio": merge_distance_ratio,
        "merge_distance_max": merge_distance_max,
        "major_component_ratio": major_component_ratio,
    }
    policy.update({key: value for key, value in direct_overrides.items() if value is not None})
    for key in ("merge_distance", "merge_distance_ratio", "merge_distance_max", "major_component_ratio"):
        policy[key] = float(policy[key])
        if float(policy[key]) < 0:
            raise ValueError(f"fragment_policy.{key} must be non-negative")
    policy["small_detached_max_pixels"] = int(policy["small_detached_max_pixels"])
    policy["small_detached_max_anchor_ratio"] = float(policy["small_detached_max_anchor_ratio"])
    if float(policy["merge_distance_max"]) < float(policy["merge_distance"]):
        raise ValueError("fragment_policy.merge_distance_max must be >= merge_distance")
    if not 0 <= float(policy["major_component_ratio"]) <= 1:
        raise ValueError("fragment_policy.major_component_ratio must be between 0 and 1")
    if int(policy["small_detached_max_pixels"]) < 0 or not 0 <= float(
        policy["small_detached_max_anchor_ratio"]
    ) <= 1:
        raise ValueError("fragment_policy detached size limits must be non-negative and ratio <= 1")
    if policy["detached_action"] not in {"warning", "allow-small"}:
        raise ValueError("fragment_policy.detached_action must be warning or allow-small")
    if policy["detached_action"] == "allow-small" and (
        int(policy["small_detached_max_pixels"]) <= 0
        or float(policy["small_detached_max_anchor_ratio"]) <= 0
    ):
        raise ValueError("allow-small requires positive detached size limits")
    return policy


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


def connected_components(
    mask: np.ndarray,
    minimum_pixels: int = 1,
    include_runs: bool = False,
) -> list[dict[str, Any]]:
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

    components: dict[int, dict[str, Any]] = {}
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
        if include_runs:
            component.setdefault("runs", []).append((y, start, end + 1))

    return sorted(
        (component for component in components.values() if component["pixels"] >= minimum_pixels),
        key=lambda component: component["pixels"],
        reverse=True,
    )


def assign_components_to_slots(
    components: list[dict[str, Any]],
    slot_centers: list[tuple[float, float]],
) -> list[list[dict[str, Any]]]:
    """Seed every slot, then attach fragments by nearest component geometry.

    Hollow frames can have a detached crest whose centroid crosses a row/column
    bisector. Slot-center-only assignment sends that crest to the neighbouring
    asset. A component whose bbox encloses the slot center is a stronger seed;
    remaining fragments then follow the nearest seeded silhouette.
    """
    assigned: list[list[dict[str, Any]]] = [[] for _ in slot_centers]
    remaining = list(components)
    for slot_index, (center_x, center_y) in enumerate(slot_centers):
        if not remaining:
            break
        containing = [
            component
            for component in remaining
            if component["left"] <= center_x < component["right"]
            and component["top"] <= center_y < component["bottom"]
        ]
        candidates = containing or remaining
        seed = min(
            candidates,
            key=lambda component: (
                0 if component in containing else 1,
                -int(component["pixels"]) if component in containing else 0,
                max(component["left"] - center_x, 0, center_x - component["right"]) ** 2
                + max(component["top"] - center_y, 0, center_y - component["bottom"]) ** 2,
                component["top"],
                component["left"],
            ),
        )
        assigned[slot_index].append(seed)
        remaining.remove(seed)

    while remaining and any(assigned):
        best: tuple[float, float, int, int] | None = None
        for component_index, component in enumerate(remaining):
            component_center = (
                (component["left"] + component["right"]) / 2.0,
                (component["top"] + component["bottom"]) / 2.0,
            )
            for slot_index, group in enumerate(assigned):
                if not group:
                    continue
                gap = min(component_gap(component, member) for member in group)
                center_distance = (
                    (component_center[0] - slot_centers[slot_index][0]) ** 2
                    + (component_center[1] - slot_centers[slot_index][1]) ** 2
                )
                candidate = (gap, center_distance, slot_index, component_index)
                if best is None or candidate < best:
                    best = candidate
        if best is None:
            break
        _, _, slot_index, component_index = best
        assigned[slot_index].append(remaining.pop(component_index))
    return assigned


def crop_assigned_components(
    source: Image.Image,
    bbox: tuple[int, int, int, int],
    components: list[dict[str, Any]],
    halo: int = 2,
) -> Image.Image:
    """Crop one asset while clearing pixels owned by neighbouring slots.

    Component ownership uses the visible Alpha threshold, but the export must
    retain the associated sub-threshold anti-aliased edge. Expand ownership by
    a small deterministic halo and intersect it with non-zero source Alpha.
    """
    left, top, right, bottom = bbox
    rgba = np.asarray(source.crop(bbox), dtype=np.uint8).copy()
    keep = np.zeros((bottom - top, right - left), dtype=bool)
    for component in components:
        for y, run_left, run_right in component.get("runs", []):
            if top <= y < bottom:
                local_left = max(left, run_left) - left
                local_right = min(right, run_right) - left
                if local_left < local_right:
                    keep[y - top, local_left:local_right] = True
    if halo > 0:
        expanded = keep.copy()
        for offset_y in range(-halo, halo + 1):
            for offset_x in range(-halo, halo + 1):
                source_top = max(0, -offset_y)
                source_bottom = keep.shape[0] - max(0, offset_y)
                source_left = max(0, -offset_x)
                source_right = keep.shape[1] - max(0, offset_x)
                target_top = max(0, offset_y)
                target_bottom = keep.shape[0] - max(0, -offset_y)
                target_left = max(0, offset_x)
                target_right = keep.shape[1] - max(0, -offset_x)
                expanded[target_top:target_bottom, target_left:target_right] |= keep[
                    source_top:source_bottom,
                    source_left:source_right,
                ]
        keep = expanded
    keep &= rgba[:, :, 3] > 0
    rgba[~keep] = 0
    return Image.fromarray(rgba, mode="RGBA")


def combined_bbox(components: list[dict[str, int]], padding: int, width: int, height: int) -> tuple[int, int, int, int]:
    left = max(0, min(component["left"] for component in components) - padding)
    top = max(0, min(component["top"] for component in components) - padding)
    right = min(width, max(component["right"] for component in components) + padding)
    bottom = min(height, max(component["bottom"] for component in components) + padding)
    return left, top, right, bottom


def touches_boundary(bbox: tuple[int, int, int, int], width: int, height: int, tolerance: int = 1) -> bool:
    left, top, right, bottom = bbox
    return left <= tolerance or top <= tolerance or right >= width - tolerance or bottom >= height - tolerance


def component_gap(left: dict[str, int], right: dict[str, int]) -> float:
    horizontal = max(0, max(left["left"], right["left"]) - min(left["right"], right["right"]))
    vertical = max(0, max(left["top"], right["top"]) - min(left["bottom"], right["bottom"]))
    return math.hypot(horizontal, vertical)


def classify_components(
    components: list[dict[str, int]],
    merge_distance: float = 12.0,
    merge_distance_ratio: float = 0.15,
    merge_distance_max: float | None = None,
    major_component_ratio: float = 0.35,
) -> dict[str, Any]:
    if not components:
        return {"anchor": None, "merged": [], "detached": [], "major_detached": []}
    ordered = sorted(components, key=lambda component: component["pixels"], reverse=True)
    merged = [ordered[0]]
    remaining = ordered[1:]
    changed = True
    while changed and remaining:
        changed = False
        group_left = min(component["left"] for component in merged)
        group_top = min(component["top"] for component in merged)
        group_right = max(component["right"] for component in merged)
        group_bottom = max(component["bottom"] for component in merged)
        diagonal = math.hypot(group_right - group_left, group_bottom - group_top)
        allowed_gap = max(merge_distance, diagonal * merge_distance_ratio)
        if merge_distance_max is not None:
            allowed_gap = min(allowed_gap, merge_distance_max)
        next_remaining: list[dict[str, int]] = []
        for component in remaining:
            nearest_gap = min(component_gap(component, member) for member in merged)
            if nearest_gap <= allowed_gap:
                merged.append(component)
                changed = True
            else:
                next_remaining.append(component)
        remaining = next_remaining
    major_detached = [
        component
        for component in remaining
        if component["pixels"] >= ordered[0]["pixels"] * major_component_ratio
    ]
    return {
        "anchor": ordered[0],
        "merged": merged,
        "detached": remaining,
        "major_detached": major_detached,
    }


def extract_assets(
    source: Image.Image,
    layout: dict[str, Any],
    request: dict[str, Any],
    output_dir: Path,
    alpha_threshold: int = 16,
    minimum_component_pixels: int = 16,
    trim_padding: int = 2,
    fragment_merge_distance: float | None = None,
    fragment_merge_distance_ratio: float | None = None,
    fragment_merge_distance_max: float | None = None,
    major_component_ratio: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = source.convert("RGBA")
    slots = layout.get("slots", [])
    assets = request.get("assets", [])
    category = request.get("category")
    if category not in CATEGORY_PREFIX:
        raise ValueError(f"unsupported category: {category}")
    fragment_policy = resolve_fragment_policy(
        category,
        request.get("fragment_policy"),
        merge_distance=fragment_merge_distance,
        merge_distance_ratio=fragment_merge_distance_ratio,
        merge_distance_max=fragment_merge_distance_max,
        major_component_ratio=major_component_ratio,
    )
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
    global_components = connected_components(
        source_alpha >= alpha_threshold,
        minimum_component_pixels,
        include_runs=True,
    )
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
        spanned_slots = [
            index + 1
            for index, (center_x, center_y) in enumerate(slot_centers)
            if component["left"] <= center_x < component["right"]
            and component["top"] <= center_y < component["bottom"]
        ]
        if len(spanned_slots) > 1:
            issues.append(
                {
                    "severity": "fail",
                    "code": "cross-slot-connected-component",
                    "source_indices": spanned_slots,
                    "bbox": [component["left"], component["top"], component["right"], component["bottom"]],
                    "pixels": component["pixels"],
                }
            )
    assigned_components = assign_components_to_slots(global_components, slot_centers)

    for visual_index, asset in enumerate(assets, start=1):
        components = assigned_components[visual_index - 1]
        category_index = int(asset.get("category_index", visual_index))
        if category_index <= 0:
            raise ValueError("asset category_index must be positive")

        if not components:
            issues.append({"severity": "fail", "code": "empty-slot", "source_index": visual_index})
            continue

        component_groups = classify_components(
            components,
            merge_distance=float(fragment_policy["merge_distance"]),
            merge_distance_ratio=float(fragment_policy["merge_distance_ratio"]),
            merge_distance_max=float(fragment_policy["merge_distance_max"]),
            major_component_ratio=float(fragment_policy["major_component_ratio"]),
        )

        accepted_detached = []
        warning_detached = list(component_groups["detached"])
        if fragment_policy["detached_action"] == "allow-small":
            anchor_pixels = max(1, int(component_groups["anchor"]["pixels"]))
            major_ids = {id(component) for component in component_groups["major_detached"]}
            accepted_detached = [
                component
                for component in component_groups["detached"]
                if id(component) not in major_ids
                and component["pixels"] <= int(fragment_policy["small_detached_max_pixels"])
                and component["pixels"] / anchor_pixels
                <= float(fragment_policy["small_detached_max_anchor_ratio"])
            ]
            accepted_ids = {id(component) for component in accepted_detached}
            warning_detached = [
                component for component in component_groups["detached"] if id(component) not in accepted_ids
            ]

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
        if accepted_detached:
            issues.append(
                {
                    "severity": "info",
                    "code": "accepted-small-detached-components",
                    "source_index": visual_index,
                    "accepted_detached_count": len(accepted_detached),
                }
            )
        if warning_detached:
            issues.append(
                {
                    "severity": "warning",
                    "code": "detached-components",
                    "source_index": visual_index,
                    "component_count": len(components),
                    "merged_component_count": len(component_groups["merged"]),
                    "detached_component_count": len(warning_detached),
                }
            )
        if component_groups["major_detached"]:
            issues.append(
                {
                    "severity": "warning",
                    "code": "multiple-major-components",
                    "source_index": visual_index,
                    "major_detached_count": len(component_groups["major_detached"]),
                }
            )

        semantic_name = pascal_case(str(asset.get("semantic_name", "")), f"Asset{visual_index:03d}")
        state = pascal_case(str(asset.get("state", "Default")), "Default")
        filename = (
            f"{CATEGORY_PREFIX[category]}_{category}_{semantic_name}_{state}_{category_index:03d}.png"
        )
        extracted = crop_assigned_components(source, bbox, components, halo=trim_padding)
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
                "merged_component_count": len(component_groups["merged"]),
                "detached_component_count": len(component_groups["detached"]),
                "accepted_detached_count": len(accepted_detached),
                "major_detached_count": len(component_groups["major_detached"]),
                "foreground_pixels": int(sum(component["pixels"] for component in components)),
                "qa": "warning" if warning_detached else "pass",
            }
        )

    failures = [issue for issue in issues if issue["severity"] == "fail"]
    warnings = [issue for issue in issues if issue["severity"] == "warning"]
    manifest = {
        "schema_version": 1,
        "project_id": request.get("project_id", "game-ui"),
        "category": category,
        "source_image_size": [source.width, source.height],
        "assignment_mode": "global-components-slot-seeded-nearest-geometry-masked",
        "fragment_policy": fragment_policy,
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
    parser.add_argument("--alpha-threshold", type=int, default=16)
    parser.add_argument("--minimum-component-pixels", type=int, default=16)
    parser.add_argument("--trim-padding", type=int, default=2)
    parser.add_argument("--fragment-merge-distance", type=float)
    parser.add_argument("--fragment-merge-distance-ratio", type=float)
    parser.add_argument("--fragment-merge-distance-max", type=float)
    parser.add_argument("--major-component-ratio", type=float)
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
        fragment_merge_distance=args.fragment_merge_distance,
        fragment_merge_distance_ratio=args.fragment_merge_distance_ratio,
        fragment_merge_distance_max=args.fragment_merge_distance_max,
        major_component_ratio=args.major_component_ratio,
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
