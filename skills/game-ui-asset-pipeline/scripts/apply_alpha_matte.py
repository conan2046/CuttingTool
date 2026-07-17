#!/usr/bin/env python3
"""Combine a rendered RGB sheet and a model-generated grayscale opacity matte."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.expanduser().resolve().open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def border_mask(width: int, height: int, thickness: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    mask[:thickness, :] = True
    mask[-thickness:, :] = True
    mask[:, :thickness] = True
    mask[:, -thickness:] = True
    return mask


def bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def bbox_iou(first: tuple[int, int, int, int] | None, second: tuple[int, int, int, int] | None) -> float:
    if first is None or second is None:
        return 0.0
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0, right - left) * max(0, bottom - top)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    return float(intersection / union) if union else 0.0


def apply_alpha_matte(
    source: Image.Image,
    matte: Image.Image,
    minimum_visible_alpha: int = 16,
    maximum_matte_channel_spread: float = 24.0,
    maximum_border_alpha: float = 24.0,
    maximum_source_border_spread: float = 28.0,
    minimum_distinct_alpha_levels: int = 8,
    minimum_partial_alpha_pixels: int = 32,
    minimum_bbox_iou: float = 0.55,
    minimum_source_coverage: float = 0.65,
    minimum_matte_support: float = 0.65,
) -> tuple[Image.Image, dict[str, Any]]:
    source_rgb = np.asarray(source.convert("RGB"), dtype=np.float32)
    matte_rgb_image = matte.convert("RGB")
    matte_resized = matte_rgb_image.size != source.size
    if matte_resized:
        matte_rgb_image = matte_rgb_image.resize(source.size, Image.Resampling.LANCZOS)
    matte_rgb = np.asarray(matte_rgb_image, dtype=np.float32)
    height, width = source_rgb.shape[:2]
    thickness = max(2, min(width, height) // 64)
    border = border_mask(width, height, thickness)

    channel_spread = np.max(matte_rgb, axis=2) - np.min(matte_rgb, axis=2)
    grayscale_spread_p95 = float(np.percentile(channel_spread, 95))
    luminance = np.clip(
        0.2126 * matte_rgb[:, :, 0] + 0.7152 * matte_rgb[:, :, 1] + 0.0722 * matte_rgb[:, :, 2],
        0,
        255,
    )
    border_alpha_p95 = float(np.percentile(luminance[border], 95))
    alpha = np.rint(luminance).astype(np.uint8)

    background_rgb = np.median(source_rgb[border], axis=0)
    border_distance = np.linalg.norm(source_rgb[border] - background_rgb.reshape(1, 3), axis=1)
    source_border_spread_p95 = float(np.percentile(border_distance, 95))
    source_distance = np.linalg.norm(source_rgb - background_rgb.reshape(1, 1, 3), axis=2)
    source_visible = source_distance >= max(12.0, source_border_spread_p95 * 1.5)
    matte_visible = alpha >= minimum_visible_alpha
    overlap = source_visible & matte_visible
    source_coverage = float(np.count_nonzero(overlap) / max(1, np.count_nonzero(source_visible)))
    matte_support = float(np.count_nonzero(overlap) / max(1, np.count_nonzero(matte_visible)))
    correspondence_iou = bbox_iou(bbox(source_visible), bbox(matte_visible))

    partial = (alpha > 0) & (alpha < 255)
    transparent = alpha == 0
    distinct_levels = int(np.unique(alpha).size)
    issues: list[dict[str, Any]] = []
    if matte_resized:
        issues.append(
            {
                "severity": "fail",
                "code": "source-matte-size-mismatch",
                "source_size": list(source.size),
                "matte_size": list(matte.size),
            }
        )
    checks = (
        (grayscale_spread_p95 <= maximum_matte_channel_spread, "matte-not-grayscale", grayscale_spread_p95),
        (border_alpha_p95 <= maximum_border_alpha, "matte-border-not-transparent", border_alpha_p95),
        (source_border_spread_p95 <= maximum_source_border_spread, "source-background-not-flat", source_border_spread_p95),
        (int(np.count_nonzero(transparent)) > 0, "matte-has-no-transparent-pixels", 0),
        (int(np.count_nonzero(partial)) >= minimum_partial_alpha_pixels, "insufficient-partial-alpha-pixels", int(np.count_nonzero(partial))),
        (distinct_levels >= minimum_distinct_alpha_levels, "insufficient-alpha-levels", distinct_levels),
        (correspondence_iou >= minimum_bbox_iou, "source-matte-bbox-mismatch", correspondence_iou),
        (
            source_coverage >= minimum_source_coverage and matte_support >= minimum_matte_support,
            "source-matte-pixel-mismatch",
            {"source_coverage_ratio": source_coverage, "matte_support_ratio": matte_support},
        ),
    )
    for passed, code, actual in checks:
        if not passed:
            issues.append({"severity": "fail", "code": code, "actual": actual})

    alpha_float = alpha.astype(np.float32) / 255.0
    foreground_premultiplied = source_rgb - (1.0 - alpha_float[:, :, None]) * background_rgb.reshape(1, 1, 3)
    foreground_premultiplied = np.clip(foreground_premultiplied, 0, 255)
    safe_alpha = np.maximum(alpha_float[:, :, None], 1.0 / 255.0)
    foreground_straight = np.clip(foreground_premultiplied / safe_alpha, 0, 255).astype(np.uint8)
    foreground_straight[alpha == 0] = 0
    rgba = np.dstack([foreground_straight, alpha])
    output = Image.fromarray(rgba, mode="RGBA")
    return output, {
        "schema_version": 1,
        "ok": not issues,
        "algorithm": "gpt-image-2-model-matte-v1",
        "alpha_origin": "gpt-image-2-matte-derived",
        "width": width,
        "height": height,
        "matte_resized_to_source": matte_resized,
        "estimated_background_rgb": [round(float(value), 3) for value in background_rgb],
        "source_border_spread_p95": source_border_spread_p95,
        "matte_grayscale_spread_p95": grayscale_spread_p95,
        "matte_border_alpha_p95": border_alpha_p95,
        "transparent_pixels": int(np.count_nonzero(transparent)),
        "partial_alpha_pixels": int(np.count_nonzero(partial)),
        "opaque_pixels": int(np.count_nonzero(alpha == 255)),
        "distinct_alpha_levels": distinct_levels,
        "source_coverage_ratio": source_coverage,
        "matte_support_ratio": matte_support,
        "source_matte_bbox_iou": correspondence_iou,
        "issues": issues,
    }
