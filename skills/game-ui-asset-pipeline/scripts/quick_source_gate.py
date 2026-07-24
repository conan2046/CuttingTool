#!/usr/bin/env python3
"""Fast deterministic checks for a newly generated source sheet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from validate_asset_pack import nine_slice_stretch_band_report


SOURCE_GATE_SCHEMA_VERSION = 3
SOURCE_GATE_CONTRACT_VERSION = "nine-slice-source-gate-v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contract_fingerprint(job: dict[str, Any], run_dir: Path, source_hash: str) -> str:
    """Bind cached verdicts to source, request, layout, mode, and gate behavior."""
    digest = hashlib.sha256()
    digest.update(SOURCE_GATE_CONTRACT_VERSION.encode("utf-8"))
    digest.update(source_hash.encode("ascii"))
    digest.update(str(job.get("transparency_mode", "chroma-key")).encode("utf-8"))
    for field in ("request_file", "layout_json"):
        relative = str(job[field])
        path = run_dir / relative
        digest.update(relative.encode("utf-8"))
        digest.update(_sha256(path).encode("ascii"))
    return digest.hexdigest()


def _hex_rgb(value: str) -> np.ndarray:
    value = value.lstrip("#")
    return np.array([int(value[index:index + 2], 16) for index in (0, 2, 4)], dtype=np.int32)


def validate_source_sheet(job: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """Check decode, aspect, occupied slots, canvas edge contact, and Status green spill."""
    source = run_dir / str(job["generated_output"])
    report_path = run_dir / "qa" / "source-gates" / f"{job['id']}.json"
    if not source.is_file():
        return {"ok": False, "status": "missing", "issues": [{"code": "source-missing"}]}
    source_hash = _sha256(source)
    contract_fingerprint = _contract_fingerprint(job, run_dir, source_hash)
    if report_path.is_file():
        cached = json.loads(report_path.read_text(encoding="utf-8"))
        if (
            cached.get("schema_version") == SOURCE_GATE_SCHEMA_VERSION
            and cached.get("contract_fingerprint") == contract_fingerprint
        ):
            return cached

    issues: list[dict[str, Any]] = []
    try:
        rgba = np.asarray(Image.open(source).convert("RGBA"), dtype=np.uint8)
    except (OSError, ValueError) as error:
        result = {
            "schema_version": SOURCE_GATE_SCHEMA_VERSION,
            "ok": False,
            "status": "failed",
            "source": str(job["generated_output"]),
            "source_sha256": source_hash,
            "contract_fingerprint": contract_fingerprint,
            "issues": [{"code": "source-decode-failed", "detail": str(error)}],
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result

    layout = json.loads((run_dir / str(job["layout_json"])).read_text(encoding="utf-8"))
    expected_width = int(layout["layout"]["width"])
    expected_height = int(layout["layout"]["height"])
    height, width = rgba.shape[:2]
    if width * expected_height != height * expected_width:
        issues.append({"code": "source-aspect-ratio-mismatch", "actual": [width, height], "expected": [expected_width, expected_height]})

    mode = str(job.get("transparency_mode", "chroma-key"))
    request = json.loads((run_dir / str(job["request_file"])).read_text(encoding="utf-8"))
    rgb = rgba[:, :, :3].astype(np.int32)
    if mode == "chroma-key":
        key = _hex_rgb(str(request["chroma_key"]))
        distance = np.sqrt(np.sum((rgb - key) ** 2, axis=2))
        foreground = distance > 48.0
    elif mode == "model-matte-derived":
        foreground = np.max(rgb, axis=2) > 20
    else:
        foreground = rgba[:, :, 3] >= 16

    border_pixels = np.concatenate((foreground[0, :], foreground[-1, :], foreground[:, 0], foreground[:, -1]))
    if int(np.count_nonzero(border_pixels)):
        issues.append({"code": "source-edge-contact", "pixels": int(np.count_nonzero(border_pixels))})

    slots = list(layout.get("slots", []))
    expected_count = int(job["expected_count"])
    occupied: list[int] = []
    foreground_counts: list[int] = []
    nine_slice_reports: list[dict[str, Any]] = []
    scale_x = width / expected_width
    scale_y = height / expected_height
    for slot in slots:
        box = slot["slot"]
        left = max(0, min(width, int(round(float(box["left"]) * scale_x))))
        right = max(left + 1, min(width, int(round(float(box["right"]) * scale_x))))
        top = max(0, min(height, int(round(float(box["top"]) * scale_y))))
        bottom = max(top + 1, min(height, int(round(float(box["bottom"]) * scale_y))))
        crop = foreground[top:bottom, left:right]
        count = int(np.count_nonzero(crop))
        foreground_counts.append(count)
        minimum = max(16, int(crop.size * 0.002))
        if count >= minimum:
            occupied.append(int(slot["index"]))
            if str(job.get("category")) in {"Panel", "Button"}:
                slot_rgba = rgba[top:bottom, left:right].copy()
                slot_rgba[:, :, 3] = np.where(crop, 255, 0).astype(np.uint8)
                slot_rgba[:, :, :3][~crop] = 0
                stretch = nine_slice_stretch_band_report(slot_rgba)
                stretch["slot_index"] = int(slot["index"])
                nine_slice_reports.append(stretch)
                if not stretch.get("ok"):
                    issues.append(
                        {
                            "code": (
                                "panel-stretch-band-decoration"
                                if str(job.get("category")) == "Panel"
                                else "button-stretch-band-decoration"
                            ),
                            "slot_index": int(slot["index"]),
                            "detail": "source sheet nine-slice stretch bands are not clean",
                        }
                    )
    expected_slots = list(range(1, expected_count + 1))
    if occupied != expected_slots:
        issues.append({"code": "source-slot-count-mismatch", "expected_slots": expected_slots, "occupied_slots": occupied})

    if str(job.get("category")) == "Icon_Status" and mode == "chroma-key" and str(request.get("chroma_key", "")).upper() == "#00FF00":
        status_mask = foreground & (rgb[:, :, 1] >= 90) & (rgb[:, :, 1] >= rgb[:, :, 0] + 35) & (rgb[:, :, 1] >= rgb[:, :, 2] + 35)
        green_pixels = int(np.count_nonzero(status_mask))
        visible_pixels = max(1, int(np.count_nonzero(foreground)))
        if green_pixels > max(12, int(visible_pixels * 0.002)):
            issues.append({"code": "status-green-reflection", "pixels": green_pixels})

    result = {
        "schema_version": SOURCE_GATE_SCHEMA_VERSION,
        "ok": not issues,
        "status": "pass" if not issues else "failed",
        "source": str(job["generated_output"]),
        "source_sha256": source_hash,
        "contract_fingerprint": contract_fingerprint,
        "checks": {
            "actual_size": [width, height],
            "expected_aspect": [expected_width, expected_height],
            "slot_detection_scale": [scale_x, scale_y],
            "expected_count": expected_count,
            "occupied_slots": occupied,
            "slot_foreground_pixels": foreground_counts,
            "nine_slice_stretch_bands": nine_slice_reports,
        },
        "issues": issues,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
