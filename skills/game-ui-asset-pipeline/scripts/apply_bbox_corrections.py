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
from PIL import Image

from extract_sheet_assets import CATEGORY_PREFIX, pascal_case
from make_contact_sheet import make_contact_sheet
from normalize_assets import normalize_image
from remove_chroma_key import parse_hex_color, remove_chroma
from validate_asset_pack import validate_pack


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

    enabled_assets = [asset for asset in corrections.get("assets", []) if asset.get("enabled", True)]
    if not enabled_assets:
        raise ValueError("correction file contains no enabled assets")
    issues: list[dict[str, Any]] = []
    for index, asset in enumerate(enabled_assets):
        bbox = [int(value) for value in asset.get("bbox", [])]
        if len(bbox) != 4 or bbox[0] < 0 or bbox[1] < 0 or bbox[2] > source.width or bbox[3] > source.height:
            raise ValueError(f"invalid bbox for source_index={asset.get('source_index')}: {bbox}")
        if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
            raise ValueError(f"empty bbox for source_index={asset.get('source_index')}: {bbox}")
        for other in enabled_assets[index + 1 :]:
            other_bbox = [int(value) for value in other.get("bbox", [])]
            if len(other_bbox) == 4 and boxes_overlap(bbox, other_bbox):
                issues.append(
                    {
                        "severity": "fail",
                        "code": "overlapping-corrections",
                        "source_indices": [asset.get("source_index"), other.get("source_index")],
                    }
                )

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
        cuts_foreground = alpha_bbox[0] == 0 or alpha_bbox[1] == 0 or alpha_bbox[2] == crop.width or alpha_bbox[3] == crop.height
        if cuts_foreground:
            issues.append({"severity": "fail", "code": "bbox-cuts-foreground", "source_index": source_index, "bbox": bbox})

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
        "manual_action_required": sorted(
            {str(issue.get("source_index") or issue.get("file") or issue.get("code")) for issue in failures}
        ),
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
