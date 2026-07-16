#!/usr/bin/env python3
"""Apply an approved bbox correction file and build a validated transparent UI asset pack."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from extract_sheet_assets import CATEGORY_PREFIX, pascal_case
from make_contact_sheet import make_contact_sheet
from normalize_assets import normalize_image
from remove_chroma_key import parse_hex_color, remove_chroma
from validate_asset_pack import validate_pack


def preview_font(width: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    size = max(12, min(24, width // 80))
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative(path: Path, root: Path) -> str:
    return path.expanduser().resolve().relative_to(root.expanduser().resolve()).as_posix()


def clean_alpha(image: Image.Image) -> Image.Image:
    array = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    array[:, :, :3][array[:, :, 3] == 0] = 0
    return Image.fromarray(array, mode="RGBA")


def prepare_transparency(source: Image.Image, background: dict[str, Any]) -> tuple[Image.Image, dict[str, Any]]:
    mode = str(background.get("mode", ""))
    if mode == "alpha":
        output = clean_alpha(source)
        return output, {"ok": output.getchannel("A").getbbox() is not None, "mode": mode}
    if mode == "flat-color":
        key = parse_hex_color(str(background.get("color", "")))
        output, report = remove_chroma(
            source,
            key,
            transparent_threshold=float(background.get("transparent_threshold", 24.0)),
            opaque_threshold=float(background.get("opaque_threshold", 96.0)),
        )
        report["mode"] = mode
        return output, report
    if mode == "checkerboard":
        raise ValueError("fake checkerboard background cannot be exported as transparency; regenerate or supply real Alpha")
    raise ValueError("correction background is unresolved; provide a real Alpha image or an approved flat color")


def boxes_overlap(left: list[int], right: list[int]) -> bool:
    return max(left[0], right[0]) < min(left[2], right[2]) and max(left[1], right[1]) < min(left[3], right[3])


def correction_issue(
    code: str,
    message: str,
    location: str,
    suggestion: str,
    **details: Any,
) -> dict[str, Any]:
    return {
        "severity": "fail",
        "code": code,
        "message": message,
        "location": location,
        "suggestion": suggestion,
        **details,
    }


def manual_action_required(issues: list[dict[str, Any]]) -> list[str]:
    references: set[str] = set()
    for item in issues:
        if item.get("source_index") is not None:
            references.add(str(item["source_index"]))
        for source_index in item.get("source_indices", []):
            references.add(str(source_index))
        if item.get("location"):
            references.add(str(item["location"]))
        elif item.get("file"):
            references.add(str(item["file"]))
        elif item.get("code"):
            references.add(str(item["code"]))
    return sorted(references)


def validate_correction_assets(
    alpha_source: Image.Image,
    corrections: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    visible_alpha_threshold = int(
        corrections.get("review_guidance", {})
        .get("threshold_suggestions", {})
        .get("bbox_visible_alpha", {})
        .get("current", 16)
    )
    enabled_with_positions = [
        (position, asset)
        for position, asset in enumerate(corrections.get("assets", []))
        if asset.get("enabled", True)
    ]
    issues: list[dict[str, Any]] = []
    valid_boxes: dict[int, list[int]] = {}
    seen_source_indices: dict[int, int] = {}
    category_indices: dict[str, list[tuple[int, int]]] = {}
    for position, asset in enabled_with_positions:
        location = f"assets[{position}]"
        try:
            source_index = int(asset.get("source_index", position + 1))
        except (TypeError, ValueError):
            source_index = position + 1
            issues.append(
                correction_issue(
                    "invalid-source-index",
                    "source_index must be an integer.",
                    f"{location}.source_index",
                    f"Set source_index to {position + 1}.",
                )
            )
        if source_index in seen_source_indices:
            issues.append(
                correction_issue(
                    "duplicate-source-index",
                    f"source_index {source_index} is used by more than one enabled asset.",
                    f"{location}.source_index",
                    "Assign a unique source_index to every enabled candidate.",
                    source_index=source_index,
                    conflicting_location=f"assets[{seen_source_indices[source_index]}].source_index",
                )
            )
        else:
            seen_source_indices[source_index] = position

        raw_bbox = asset.get("bbox", [])
        try:
            bbox = [int(value) for value in raw_bbox]
        except (TypeError, ValueError):
            bbox = []
        if len(bbox) != 4:
            issues.append(
                correction_issue(
                    "invalid-bbox-shape",
                    "bbox must contain exactly four integer coordinates.",
                    f"{location}.bbox",
                    "Use [left, top, right, bottom] with right/bottom exclusive.",
                    source_index=source_index,
                    bbox=raw_bbox,
                )
            )
            continue
        clamped = [
            max(0, min(alpha_source.width, bbox[0])),
            max(0, min(alpha_source.height, bbox[1])),
            max(0, min(alpha_source.width, bbox[2])),
            max(0, min(alpha_source.height, bbox[3])),
        ]
        if bbox[0] < 0 or bbox[1] < 0 or bbox[2] > alpha_source.width or bbox[3] > alpha_source.height:
            issues.append(
                correction_issue(
                    "bbox-out-of-bounds",
                    f"bbox {bbox} exceeds image bounds {[alpha_source.width, alpha_source.height]}.",
                    f"{location}.bbox",
                    f"Clamp to {clamped}, then verify the candidate is still complete.",
                    source_index=source_index,
                    bbox=bbox,
                    recommended_bbox=clamped,
                )
            )
            continue
        if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
            issues.append(
                correction_issue(
                    "empty-bbox",
                    f"bbox {bbox} has zero or negative area.",
                    f"{location}.bbox",
                    "Set right > left and bottom > top around one visible asset.",
                    source_index=source_index,
                    bbox=bbox,
                )
            )
            continue
        valid_boxes[position] = bbox

        category = str(asset.get("category", ""))
        if category not in CATEGORY_PREFIX:
            issues.append(
                correction_issue(
                    "unsupported-category",
                    f"Unsupported internal category: {category!r}.",
                    f"{location}.category",
                    "Use one of: " + ", ".join(sorted(CATEGORY_PREFIX)),
                    source_index=source_index,
                )
            )
        try:
            category_index = int(asset.get("category_index"))
            category_indices.setdefault(category, []).append((position, category_index))
        except (TypeError, ValueError):
            issues.append(
                correction_issue(
                    "invalid-category-index",
                    "category_index must be an integer.",
                    f"{location}.category_index",
                    "Assign continuous category indices starting at 1.",
                    source_index=source_index,
                )
            )

    for left_offset, (left_position, left_asset) in enumerate(enabled_with_positions):
        left_bbox = valid_boxes.get(left_position)
        if left_bbox is None:
            continue
        for right_position, right_asset in enabled_with_positions[left_offset + 1 :]:
            right_bbox = valid_boxes.get(right_position)
            if right_bbox is not None and boxes_overlap(left_bbox, right_bbox):
                issues.append(
                    correction_issue(
                        "overlapping-corrections",
                        "Two enabled bboxes overlap.",
                        f"assets[{left_position}].bbox <-> assets[{right_position}].bbox",
                        "Move or shrink the boxes so each visible resource belongs to exactly one candidate.",
                        source_indices=[left_asset.get("source_index"), right_asset.get("source_index")],
                        bboxes=[left_bbox, right_bbox],
                    )
                )

    for category, values in category_indices.items():
        if category not in CATEGORY_PREFIX:
            continue
        actual = sorted(value for _, value in values)
        expected = list(range(1, len(values) + 1))
        if actual != expected:
            for position, value in values:
                issues.append(
                    correction_issue(
                        "non-continuous-category-index",
                        f"Category {category} indices are {actual}; expected {expected}.",
                        f"assets[{position}].category_index",
                        "Renumber enabled assets continuously from 1 in reading order.",
                        source_index=corrections["assets"][position].get("source_index"),
                        actual=value,
                        expected=expected,
                    )
                )

    for position, asset in enabled_with_positions:
        bbox = valid_boxes.get(position)
        if bbox is None:
            continue
        crop = alpha_source.crop(tuple(bbox))
        alpha = np.asarray(crop.getchannel("A"), dtype=np.uint8)
        visible = alpha >= visible_alpha_threshold
        visible_image = Image.fromarray((visible.astype(np.uint8) * 255), mode="L")
        alpha_bbox = visible_image.getbbox()
        source_index = int(asset.get("source_index", position + 1))
        if alpha_bbox is None:
            issues.append(
                correction_issue(
                    "empty-correction",
                    "The bbox contains no visible foreground after background cleanup.",
                    f"assets[{position}].bbox",
                    "Move the bbox onto the marked candidate or disable this asset.",
                    source_index=source_index,
                    bbox=bbox,
                )
            )
            continue
        touches = [
            side
            for side, value in zip(
                ("left", "top", "right", "bottom"),
                (alpha_bbox[0] == 0, alpha_bbox[1] == 0, alpha_bbox[2] == crop.width, alpha_bbox[3] == crop.height),
            )
            if value
        ]
        if touches:
            margin = 4
            recommended = [
                max(0, bbox[0] - (margin if "left" in touches else 0)),
                max(0, bbox[1] - (margin if "top" in touches else 0)),
                min(alpha_source.width, bbox[2] + (margin if "right" in touches else 0)),
                min(alpha_source.height, bbox[3] + (margin if "bottom" in touches else 0)),
            ]
            issues.append(
                correction_issue(
                    "bbox-cuts-foreground",
                    "Visible foreground touches bbox edge(s): " + ", ".join(touches) + ".",
                    f"assets[{position}].bbox",
                    f"Expand toward the marked edge(s), starting with {recommended}; if already at canvas edge, replace the cropped source.",
                    source_index=source_index,
                    bbox=bbox,
                    touched_edges=touches,
                    recommended_bbox=recommended,
                    suggested_safety_margin=margin,
                    visible_alpha_threshold=visible_alpha_threshold,
                )
            )
    return [asset for _, asset in enabled_with_positions], issues


def render_correction_diff(
    source: Image.Image,
    corrections: dict[str, Any],
    issues: list[dict[str, Any]],
    output: Path,
) -> None:
    base = source.convert("RGB")
    header = 32
    preview = Image.new("RGB", (base.width * 2, base.height + header), "#111827")
    preview.paste(base, (0, header))
    preview.paste(base, (base.width, header))
    draw = ImageDraw.Draw(preview)
    font = preview_font(base.width)
    draw.text((8, 10), "BEFORE: detected bbox", fill="#93C5FD", font=font)
    draw.text((base.width + 8, 10), "AFTER: approved correction", fill="#86EFAC", font=font)
    failing_indices = {
        str(value)
        for item in issues
        for value in ([item.get("source_index")] + list(item.get("source_indices", [])))
        if value is not None
    }
    for position, asset in enumerate(corrections.get("assets", [])):
        if not asset.get("enabled", True):
            continue
        source_index = asset.get("source_index", position + 1)
        original = asset.get("detected_bbox", asset.get("bbox", []))
        corrected = asset.get("bbox", [])
        if len(original) == 4:
            draw.rectangle(
                (original[0], original[1] + header, max(original[0], original[2] - 1), max(original[1] + header, original[3] + header - 1)),
                outline="#60A5FA",
                width=3,
            )
            draw.text((original[0] + 2, original[1] + header + 2), f"#{int(source_index):03d}", fill="#FFFFFF", font=font)
        if len(corrected) == 4:
            offset = base.width
            color = "#EF4444" if str(source_index) in failing_indices else "#22C55E"
            draw.rectangle(
                (
                    corrected[0] + offset,
                    corrected[1] + header,
                    max(corrected[0] + offset, corrected[2] + offset - 1),
                    max(corrected[1] + header, corrected[3] + header - 1),
                ),
                outline=color,
                width=3,
            )
            changed = " changed" if list(original) != list(corrected) else " unchanged"
            draw.text(
                (corrected[0] + offset + 2, corrected[1] + header + 2),
                f"#{int(source_index):03d}{changed}",
                fill="#FFFFFF",
                font=font,
            )
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    preview.save(output, format="PNG")


def apply_corrections(
    source: Image.Image,
    corrections: dict[str, Any],
    run_dir: Path,
    project_id: str,
    source_sheet: str,
    force: bool = False,
) -> dict[str, Any]:
    if not corrections.get("approved", False):
        raise ValueError("bbox corrections must set approved=true after visual review")
    run_dir = run_dir.expanduser().resolve()
    final_manifest_path = run_dir / "final" / "manifest.json"
    if final_manifest_path.exists() and not force:
        raise FileExistsError(f"final manifest already exists: {final_manifest_path}; use --force to rerun")
    image_size = corrections.get("image_size")
    if image_size and [source.width, source.height] != [int(image_size[0]), int(image_size[1])]:
        raise ValueError(f"source size {source.size} does not match correction image_size {image_size}")
    alpha_source, background_report = prepare_transparency(source, corrections.get("background", {}))

    enabled_assets, preflight_issues = validate_correction_assets(alpha_source, corrections)
    if not enabled_assets:
        raise ValueError("correction file contains no enabled assets")
    qa_dir = run_dir / "qa"
    diff_path = qa_dir / "bbox-diff-preview.png"
    render_correction_diff(source, corrections, preflight_issues, diff_path)
    correction_validation_path = qa_dir / "correction-validation.json"
    correction_validation = {
        "schema_version": 2,
        "ok": not preflight_issues,
        "error_count": len(preflight_issues),
        "issues": preflight_issues,
        "threshold_suggestions": corrections.get("review_guidance", {}).get("threshold_suggestions", {}),
        "difference_preview": relative(diff_path, run_dir),
    }
    write_json(correction_validation_path, correction_validation)
    if preflight_issues:
        actions = manual_action_required(preflight_issues)
        qa_report = {
            "schema_version": 2,
            "ok": False,
            "expected_count": len(enabled_assets),
            "manifest_count": 0,
            "valid_assets": 0,
            "pass_count": 0,
            "warning_count": 0,
            "fail_count": len(preflight_issues),
            "issues": preflight_issues,
            "manual_action_required": actions,
            "correction_validation": relative(correction_validation_path, run_dir),
            "difference_preview": relative(diff_path, run_dir),
        }
        qa_path = qa_dir / "qa-report.json"
        write_json(qa_path, qa_report)
        summary = {
            "schema_version": 2,
            "project_id": project_id,
            "status": "failed",
            "source_mode": "bbox-corrections",
            "pipeline": {
                "manifest": None,
                "contact_sheet": None,
                "qa_report": relative(qa_path, run_dir),
                "correction_validation": relative(correction_validation_path, run_dir),
                "bbox_difference_preview": relative(diff_path, run_dir),
            },
            "results": {
                "expected": len(enabled_assets),
                "exported": 0,
                "pass": 0,
                "warning": 0,
                "fail": len(preflight_issues),
                "manual_action_required": actions,
            },
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json(qa_dir / "run-summary.json", summary)
        return {"ok": False, "run_dir": str(run_dir), **summary["results"]}

    issues: list[dict[str, Any]] = []

    normalization = corrections.get("normalization", {})
    entries: list[dict[str, Any]] = []
    seen_outputs: set[str] = set()
    for ordinal, asset in enumerate(enabled_assets, start=1):
        source_index = int(asset.get("source_index", ordinal))
        category_index = int(asset.get("category_index", ordinal))
        category = str(asset.get("category", ""))
        if category not in CATEGORY_PREFIX:
            raise ValueError(f"unsupported category in source_index={source_index}: {category}")
        semantic_name = pascal_case(str(asset.get("semantic_name", "")), f"Asset{category_index:03d}")
        state = pascal_case(str(asset.get("state", "Default")), "Default")
        bbox = [int(value) for value in asset["bbox"]]
        crop = alpha_source.crop(tuple(bbox))
        alpha_bbox = crop.getchannel("A").getbbox()
        if alpha_bbox is None:
            issues.append({"severity": "fail", "code": "empty-correction", "source_index": source_index})
            continue
        cuts_foreground = False

        target_value = asset.get("target_size", normalization.get("target_size"))
        target_size = tuple(int(value) for value in target_value) if target_value else None
        padding = int(asset.get("padding", normalization.get("padding", 8)))
        alignment = str(asset.get("alignment", normalization.get("alignment", "center")))
        allow_upscale = bool(asset.get("allow_upscale", normalization.get("allow_upscale", False)))
        normalized, metadata = normalize_image(crop, target_size, padding, alignment, allow_upscale=allow_upscale)
        filename = f"{CATEGORY_PREFIX[category]}_{category}_{semantic_name}_{state}_{category_index:03d}.png"
        output_path = run_dir / "final" / category / filename
        output_relative = relative(output_path, run_dir)
        if output_relative in seen_outputs or (output_path.exists() and not force):
            issues.append({"severity": "fail", "code": "duplicate-output", "file": output_relative})
            continue
        seen_outputs.add(output_relative)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        normalized.save(output_path, format="PNG")
        entry_qa = "fail" if cuts_foreground else "pass"
        entries.append(
            {
                "id": output_path.stem,
                "category": category,
                "semantic_name": semantic_name,
                "state": state,
                "source_sheet": source_sheet,
                "source_index": source_index,
                "category_index": category_index,
                "source_bbox": bbox,
                "output": output_relative,
                "width": normalized.width,
                "height": normalized.height,
                "padding": padding,
                "alignment": alignment,
                "pivot": [0.5, 0.0] if alignment == "bottom-center" else [0.5, 0.5],
                "chroma_key": corrections.get("background", {}).get("color")
                if corrections.get("background", {}).get("mode") == "flat-color"
                else None,
                "normalization": metadata,
                "qa": entry_qa,
            }
        )

    entries.sort(key=lambda entry: (entry["id"][:2], entry["category_index"]))
    manifest = {
        "schema_version": 2,
        "project_id": project_id,
        "stage": "final",
        "source_mode": "bbox-corrections",
        "expected_count": len(enabled_assets),
        "exported_count": len(entries),
        "assets": entries,
    }
    write_json(final_manifest_path, manifest)
    contact_path = run_dir / "qa" / "contact-sheet.png"
    contact_report = make_contact_sheet(manifest, run_dir, contact_path)
    validation = validate_pack(manifest, run_dir, strict_files=True)
    issues.extend(validation.get("issues", []))
    if not background_report.get("ok", False):
        issues.append({"severity": "fail", "code": "background-cleanup-failed"})
    failures = [issue for issue in issues if issue.get("severity") == "fail"]
    warnings = [issue for issue in issues if issue.get("severity") == "warning"]
    qa_report = {
        "schema_version": 2,
        "ok": not failures and validation.get("ok", False) and contact_report.get("ok", False),
        "expected_count": len(enabled_assets),
        "manifest_count": len(entries),
        "valid_assets": validation.get("valid_assets", 0),
        "pass_count": sum(entry["qa"] == "pass" for entry in entries),
        "warning_count": len(warnings),
        "fail_count": len(failures),
        "issues": issues,
        "manual_action_required": manual_action_required(failures),
        "correction_validation": relative(correction_validation_path, run_dir),
        "difference_preview": relative(diff_path, run_dir),
    }
    qa_path = run_dir / "qa" / "qa-report.json"
    write_json(qa_path, qa_report)
    write_json(run_dir / "qa" / "background-report.json", background_report)
    summary = {
        "schema_version": 2,
        "project_id": project_id,
        "status": "complete" if qa_report["ok"] else "failed",
        "source_mode": "bbox-corrections",
        "pipeline": {
            "manifest": relative(final_manifest_path, run_dir),
            "contact_sheet": relative(contact_path, run_dir),
            "qa_report": relative(qa_path, run_dir),
            "correction_validation": relative(correction_validation_path, run_dir),
            "bbox_difference_preview": relative(diff_path, run_dir),
        },
        "results": {
            "expected": len(enabled_assets),
            "exported": len(entries),
            "pass": qa_report["pass_count"],
            "warning": qa_report["warning_count"],
            "fail": qa_report["fail_count"],
            "manual_action_required": qa_report["manual_action_required"],
        },
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(run_dir / "qa" / "run-summary.json", summary)
    return {"ok": qa_report["ok"], "run_dir": str(run_dir), **summary["results"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--corrections", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    input_path = args.input.expanduser().resolve()
    corrections = read_json(args.corrections)
    run_dir = args.run_dir.expanduser().resolve()
    source_path = run_dir / "generated" / f"diagnosed-source{input_path.suffix.lower()}"
    if input_path != source_path:
        if source_path.exists() and not args.force:
            raise FileExistsError(f"source copy already exists: {source_path}; use --force to rerun")
        source_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_path, source_path)
    elif not source_path.is_file():
        raise FileNotFoundError(f"input image not found: {source_path}")
    write_json(run_dir / "qa" / "bbox-corrections.json", corrections)
    with Image.open(source_path) as image:
        source = image.convert("RGBA")
    result = apply_corrections(
        source,
        corrections,
        run_dir,
        args.project_id,
        relative(source_path, run_dir),
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
