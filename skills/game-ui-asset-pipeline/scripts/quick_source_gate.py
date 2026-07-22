#!/usr/bin/env python3
"""Fast deterministic checks for a newly generated source sheet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
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
    if report_path.is_file():
        cached = json.loads(report_path.read_text(encoding="utf-8"))
        if cached.get("source_sha256") == source_hash:
            return cached

    issues: list[dict[str, Any]] = []
    try:
        rgba = np.asarray(Image.open(source).convert("RGBA"), dtype=np.uint8)
    except (OSError, ValueError) as error:
        result = {
            "schema_version": 1,
            "ok": False,
            "status": "failed",
            "source": str(job["generated_output"]),
            "source_sha256": source_hash,
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
    for slot in slots:
        box = slot["slot"]
        crop = foreground[int(box["top"]):int(box["bottom"]), int(box["left"]):int(box["right"])]
        count = int(np.count_nonzero(crop))
        foreground_counts.append(count)
        minimum = max(16, int(crop.size * 0.002))
        if count >= minimum:
            occupied.append(int(slot["index"]))
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
        "schema_version": 1,
        "ok": not issues,
        "status": "pass" if not issues else "failed",
        "source": str(job["generated_output"]),
        "source_sha256": source_hash,
        "checks": {
            "actual_size": [width, height],
            "expected_aspect": [expected_width, expected_height],
            "expected_count": expected_count,
            "occupied_slots": occupied,
            "slot_foreground_pixels": foreground_counts,
        },
        "issues": issues,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
