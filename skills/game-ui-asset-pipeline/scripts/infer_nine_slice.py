#!/usr/bin/env python3
"""Infer conservative Unity 9-slice borders from a single RGBA UI asset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def _premultiplied_rgba(image: Image.Image) -> np.ndarray:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32) / 255.0
    rgba[:, :, :3] *= rgba[:, :, 3:4]
    return rgba


def _axis_candidate(array: np.ndarray, axis: int, minimum_border: int) -> dict[str, Any]:
    length = array.shape[1] if axis == 1 else array.shape[0]
    signatures = np.moveaxis(array, axis, 0).reshape(length, -1)
    center = length // 2
    reference_start = max(0, center - 1)
    reference_end = min(length, center + 2)
    reference = np.median(signatures[reference_start:reference_end], axis=0)
    distances = np.mean(np.abs(signatures - reference), axis=1)
    central = distances[length // 4 : max(length // 4 + 1, length - length // 4)]
    threshold = float(max(0.025, np.percentile(central, 65) * 1.8 + 0.01))
    stretchable = distances <= threshold

    start = center
    end = center
    gap_budget = 1
    gaps = 0
    while start > 0:
        next_value = bool(stretchable[start - 1])
        if not next_value:
            gaps += 1
            if gaps > gap_budget:
                break
        start -= 1
    gaps = 0
    while end < length - 1:
        next_value = bool(stretchable[end + 1])
        if not next_value:
            gaps += 1
            if gaps > gap_budget:
                break
        end += 1

    left = start
    right = length - 1 - end
    stretch_length = end - start + 1
    maximum_border = max(minimum_border, int(length * 0.45))
    valid_geometry = (
        left >= minimum_border
        and right >= minimum_border
        and left <= maximum_border
        and right <= maximum_border
        and stretch_length >= max(4, int(length * 0.15))
    )
    symmetry = 1.0 - min(1.0, abs(left - right) / max(1.0, float(max(left, right))))
    uniformity = 1.0 - min(1.0, float(np.mean(distances[start : end + 1])) / max(threshold, 1e-6))
    outside = np.concatenate((distances[:start], distances[end + 1 :]))
    edge_signal = 0.0 if outside.size == 0 else min(1.0, float(np.mean(outside)) / max(threshold * 1.5, 1e-6))
    stretch_score = min(1.0, stretch_length / max(1.0, length * 0.45))
    confidence = 0.30 * symmetry + 0.25 * uniformity + 0.25 * edge_signal + 0.20 * stretch_score
    if not valid_geometry:
        confidence *= 0.35
    return {
        "leading": int(left),
        "trailing": int(right),
        "stretch_start": int(start),
        "stretch_end": int(end),
        "threshold": round(threshold, 6),
        "confidence": round(float(confidence), 4),
        "valid_geometry": bool(valid_geometry),
    }


def infer_nine_slice(
    image: Image.Image,
    minimum_border: int = 4,
    minimum_confidence: float = 0.65,
) -> dict[str, Any]:
    if minimum_border < 1:
        raise ValueError("minimum_border must be positive")
    if not 0.0 <= minimum_confidence <= 1.0:
        raise ValueError("minimum_confidence must be between 0 and 1")
    array = _premultiplied_rgba(image)
    height, width = array.shape[:2]
    if width < minimum_border * 4 or height < minimum_border * 4:
        return {
            "ok": False,
            "apply": False,
            "confidence": 0.0,
            "border": [0, 0, 0, 0],
            "issues": ["image-too-small-for-nine-slice"],
        }

    horizontal = _axis_candidate(array, axis=1, minimum_border=minimum_border)
    vertical = _axis_candidate(array, axis=0, minimum_border=minimum_border)
    confidence = min(float(horizontal["confidence"]), float(vertical["confidence"]))
    apply = (
        horizontal["valid_geometry"]
        and vertical["valid_geometry"]
        and confidence >= minimum_confidence
    )
    # Unity order: left, bottom, right, top.
    border = [
        horizontal["leading"],
        vertical["trailing"],
        horizontal["trailing"],
        vertical["leading"],
    ] if apply else [0, 0, 0, 0]
    issues = [] if apply else ["nine-slice-low-confidence-manual-override-required"]
    return {
        "ok": apply,
        "apply": apply,
        "confidence": round(confidence, 4),
        "border": border,
        "horizontal": horizontal,
        "vertical": vertical,
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument("--minimum-border", type=int, default=4)
    parser.add_argument("--minimum-confidence", type=float, default=0.65)
    args = parser.parse_args()
    with Image.open(args.input.expanduser().resolve()) as image:
        result = infer_nine_slice(image, args.minimum_border, args.minimum_confidence)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
