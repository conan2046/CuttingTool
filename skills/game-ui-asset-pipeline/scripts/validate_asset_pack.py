#!/usr/bin/env python3
"""Validate a normalized transparent game UI asset pack against its manifest."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter


FILENAME_PATTERN = re.compile(
    r"^(0[1-9])_(Panel|Button|Icon_Nav|Icon_Status|Icon_General|Icon_Item|Icon_Equip|Icon_Skill|Icon_Effect)_[A-Za-z0-9]+_[A-Za-z0-9]+_\d{3}\.png$"
)

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


def parse_key(value: str | None) -> np.ndarray | None:
    if not value:
        return None
    match = re.fullmatch(r"#([0-9A-Fa-f]{6})", value)
    if not match:
        raise ValueError(f"invalid chroma key in request: {value}")
    encoded = match.group(1)
    return np.asarray([int(encoded[index : index + 2], 16) for index in (0, 2, 4)], dtype=np.float32)


def chroma_spill_score(rgb: np.ndarray, key: np.ndarray) -> np.ndarray:
    high = np.flatnonzero(key >= 240)
    low = np.flatnonzero(key <= 15)
    if high.size == 1 and low.size >= 1:
        return rgb[:, :, high[0]] - np.max(rgb[:, :, low], axis=2)
    if high.size >= 2 and low.size >= 1:
        return np.min(rgb[:, :, high], axis=2) - np.max(rgb[:, :, low], axis=2)
    return np.zeros(rgb.shape[:2], dtype=np.float32)


def validate_pack(
    manifest: dict[str, Any],
    asset_root: Path,
    request: dict[str, Any] | None = None,
    chroma_distance_threshold: float = 12.0,
    minimum_visible_alpha: int = 16,
    chroma_spill_threshold: float = 40.0,
    maximum_visible_chroma_spill_pixels: int = 16,
    strict_files: bool = False,
) -> dict[str, Any]:
    asset_root = asset_root.expanduser().resolve()
    issues: list[dict[str, Any]] = []
    entries = manifest.get("assets", [])
    expected_count = int(manifest.get("expected_count", len(entries)))
    seen_names: set[str] = set()
    referenced_files: set[str] = set()
    category_indices: dict[str, list[int]] = {}
    chroma_key = parse_key(request.get("chroma_key") if request else None)

    if len(entries) != expected_count:
        issues.append(
            {
                "severity": "fail",
                "code": "count-mismatch",
                "expected": expected_count,
                "actual": len(entries),
            }
        )

    valid_assets = 0
    for entry in entries:
        filename = str(entry.get("output", ""))
        if filename in seen_names:
            issues.append({"severity": "fail", "code": "duplicate-output", "file": filename})
            continue
        seen_names.add(filename)
        referenced_files.add(filename.replace("\\", "/"))
        if not FILENAME_PATTERN.fullmatch(Path(filename).name):
            issues.append({"severity": "fail", "code": "invalid-filename", "file": filename})
        category = str(entry.get("category", ""))
        expected_prefix = CATEGORY_PREFIX.get(category)
        if expected_prefix and not Path(filename).name.startswith(f"{expected_prefix}_{category}_"):
            issues.append({"severity": "fail", "code": "category-prefix-mismatch", "file": filename})
        category_index = int(entry.get("category_index", entry.get("source_index", 0)))
        if category_index > 0:
            category_indices.setdefault(category, []).append(category_index)
        path = asset_root / filename
        if not path.is_file():
            issues.append({"severity": "fail", "code": "missing-file", "file": filename})
            continue

        with Image.open(path) as image:
            if image.mode != "RGBA":
                issues.append({"severity": "fail", "code": "not-rgba", "file": filename, "mode": image.mode})
                rgba = image.convert("RGBA")
            else:
                rgba = image.copy()
        array = np.asarray(rgba, dtype=np.uint8)
        alpha = array[:, :, 3]
        if not np.any(alpha > 0):
            issues.append({"severity": "fail", "code": "empty-alpha", "file": filename})
            continue
        if not np.any(alpha == 0):
            issues.append({"severity": "warning", "code": "no-transparent-padding", "file": filename})
        hidden_rgb = array[:, :, :3][alpha == 0]
        if hidden_rgb.size and np.any(hidden_rgb != 0):
            issues.append({"severity": "fail", "code": "hidden-rgb-under-zero-alpha", "file": filename})
        if [rgba.width, rgba.height] != [int(entry.get("width", rgba.width)), int(entry.get("height", rgba.height))]:
            issues.append(
                {
                    "severity": "fail",
                    "code": "dimension-mismatch",
                    "file": filename,
                    "manifest": [entry.get("width"), entry.get("height")],
                    "actual": [rgba.width, rgba.height],
                }
            )
        entry_chroma_key = parse_key(entry.get("chroma_key"))
        if entry_chroma_key is None:
            entry_chroma_key = chroma_key
        if entry_chroma_key is not None:
            # Resampling RGBA art can create a few alpha=1..15 edge pixels
            # whose straight RGB remains close to the removed key. They are
            # mathematically non-zero but not visibly contaminating the edge.
            # Keep the threshold low so genuinely visible key residue still
            # fails while avoiding false failures from sub-visible coverage.
            visible = alpha >= minimum_visible_alpha
            distance = np.linalg.norm(array[:, :, :3].astype(np.float32) - entry_chroma_key.reshape(1, 1, 3), axis=2)
            near_key_count = int(np.count_nonzero(visible & (distance <= chroma_distance_threshold)))
            if near_key_count:
                issues.append(
                    {
                        "severity": "fail",
                        "code": "visible-chroma-residue",
                        "file": filename,
                        "pixels": near_key_count,
                    }
                )
            spill_score = chroma_spill_score(array[:, :, :3].astype(np.float32), entry_chroma_key)
            spill_count = int(
                np.count_nonzero(
                    visible
                    & (spill_score >= chroma_spill_threshold)
                )
            )
            if spill_count > maximum_visible_chroma_spill_pixels:
                issues.append(
                    {
                        "severity": "fail",
                        "code": "visible-chroma-spill",
                        "file": filename,
                        "pixels": spill_count,
                    }
                )
        if entry.get("transparency_mode") == "native-alpha-required":
            if entry.get("alpha_origin") != "model-native":
                issues.append({"severity": "fail", "code": "native-alpha-origin-missing", "file": filename})
            if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("source_sha256", ""))):
                issues.append({"severity": "fail", "code": "native-alpha-source-hash-missing", "file": filename})
            if not str(entry.get("alpha_provenance", "")).endswith(".provenance.json"):
                issues.append({"severity": "fail", "code": "native-alpha-provenance-missing", "file": filename})
            elif not (asset_root / str(entry["alpha_provenance"])).is_file():
                issues.append({"severity": "fail", "code": "native-alpha-provenance-file-missing", "file": filename})
            partial_count = int(np.count_nonzero((alpha > 0) & (alpha < 255)))
            if partial_count == 0 or np.unique(alpha).size < 8:
                issues.append(
                    {
                        "severity": "fail",
                        "code": "native-alpha-layering-lost",
                        "file": filename,
                        "partial_alpha_pixels": partial_count,
                        "distinct_alpha_levels": int(np.unique(alpha).size),
                    }
                )
        if entry.get("transparency_mode") == "model-matte-derived":
            if entry.get("alpha_origin") != "gpt-image-2-matte-derived":
                issues.append({"severity": "fail", "code": "model-matte-origin-missing", "file": filename})
            for field in ("source_sha256", "alpha_matte_sha256"):
                if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get(field, ""))):
                    issues.append({"severity": "fail", "code": f"{field.replace('_', '-')}-missing", "file": filename})
            matte_relative = str(entry.get("alpha_matte", ""))
            if not matte_relative.endswith("-alpha-matte.png"):
                issues.append({"severity": "fail", "code": "alpha-matte-path-missing", "file": filename})
            elif not (asset_root / matte_relative).is_file():
                issues.append({"severity": "fail", "code": "alpha-matte-file-missing", "file": filename})
            partial_count = int(np.count_nonzero((alpha > 0) & (alpha < 255)))
            if partial_count == 0 or np.unique(alpha).size < 8:
                issues.append(
                    {
                        "severity": "fail",
                        "code": "model-matte-layering-lost",
                        "file": filename,
                        "partial_alpha_pixels": partial_count,
                        "distinct_alpha_levels": int(np.unique(alpha).size),
                    }
                )
        valid_assets += 1

    for category, indices in sorted(category_indices.items()):
        expected_indices = list(range(1, len(indices) + 1))
        if sorted(indices) != expected_indices:
            issues.append(
                {
                    "severity": "fail",
                    "code": "non-continuous-category-indices",
                    "category": category,
                    "expected": expected_indices,
                    "actual": sorted(indices),
                }
            )

    scoped_roots = {
        Path(relative).parts[0] if len(Path(relative).parts) > 1 else "." for relative in referenced_files
    }
    actual_files: set[str] = set()
    for relative_root in sorted(scoped_roots):
        scan_root = asset_root if relative_root == "." else asset_root / relative_root
        if not scan_root.exists():
            continue
        actual_files.update(
            str(path.relative_to(asset_root)).replace("\\", "/")
            for path in scan_root.rglob("*.png")
            if path.is_file()
        )
    unexpected = sorted(actual_files - referenced_files)
    if unexpected:
        issues.append(
            {
                "severity": "fail" if strict_files else "warning",
                "code": "unexpected-files",
                "files": unexpected,
            }
        )

    failures = [issue for issue in issues if issue["severity"] == "fail"]
    warnings = [issue for issue in issues if issue["severity"] == "warning"]
    return {
        "schema_version": 1,
        "ok": not failures and valid_assets == len(entries),
        "expected_count": expected_count,
        "manifest_count": len(entries),
        "valid_assets": valid_assets,
        "pass_count": max(0, len(entries) - len({issue.get("file") for issue in issues if issue.get("file")})),
        "warning_count": len(warnings),
        "fail_count": len(failures),
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--asset-root", required=True, type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument("--chroma-distance-threshold", type=float, default=12.0)
    parser.add_argument("--minimum-visible-alpha", type=int, default=16)
    parser.add_argument("--chroma-spill-threshold", type=float, default=40.0)
    parser.add_argument("--maximum-visible-chroma-spill-pixels", type=int, default=16)
    parser.add_argument("--strict-files", action="store_true")
    args = parser.parse_args()
    report = validate_pack(
        read_json(args.manifest),
        args.asset_root,
        read_json(args.request) if args.request else None,
        chroma_distance_threshold=args.chroma_distance_threshold,
        minimum_visible_alpha=args.minimum_visible_alpha,
        chroma_spill_threshold=args.chroma_spill_threshold,
        maximum_visible_chroma_spill_pixels=args.maximum_visible_chroma_spill_pixels,
        strict_files=args.strict_files,
    )
    write_json(args.json_out, report)
    print(json.dumps(report, ensure_ascii=False))
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
