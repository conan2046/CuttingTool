#!/usr/bin/env python3
"""Convert a flat chroma-key background to alpha and decontaminate edge RGB."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter


def parse_hex_color(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"#?([0-9A-Fa-f]{6})", value.strip())
    if not match:
        raise argparse.ArgumentTypeError("color must use #RRGGBB format")
    encoded = match.group(1)
    return tuple(int(encoded[index : index + 2], 16) for index in (0, 2, 4))


def format_hex(color: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{channel:02X}" for channel in color)


def chroma_spill_score(rgb: np.ndarray, key: tuple[int, int, int]) -> np.ndarray:
    key_channels = np.asarray(key, dtype=np.uint8)
    high = np.flatnonzero(key_channels >= 240)
    low = np.flatnonzero(key_channels <= 15)
    if high.size == 1 and low.size >= 1:
        return rgb[:, :, high[0]] - np.max(rgb[:, :, low], axis=2)
    if high.size >= 2 and low.size >= 1:
        return np.min(rgb[:, :, high], axis=2) - np.max(rgb[:, :, low], axis=2)
    return np.zeros(rgb.shape[:2], dtype=np.float32)


def sample_border_key(rgb: np.ndarray, border_width: int = 8) -> tuple[int, int, int]:
    height, width, _ = rgb.shape
    border_width = max(1, min(border_width, max(1, min(height, width) // 4)))
    samples = np.concatenate(
        [
            rgb[:border_width, :, :].reshape(-1, 3),
            rgb[-border_width:, :, :].reshape(-1, 3),
            rgb[:, :border_width, :].reshape(-1, 3),
            rgb[:, -border_width:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    median = np.median(samples, axis=0)
    return tuple(int(round(value)) for value in median)


def border_pixels(rgb: np.ndarray, border_width: int = 8) -> np.ndarray:
    height, width, _ = rgb.shape
    border_width = max(1, min(border_width, max(1, min(height, width) // 4)))
    return np.concatenate(
        [
            rgb[:border_width, :, :].reshape(-1, 3),
            rgb[-border_width:, :, :].reshape(-1, 3),
            rgb[:, :border_width, :].reshape(-1, 3),
            rgb[:, -border_width:, :].reshape(-1, 3),
        ],
        axis=0,
    )


def recommend_chroma_thresholds(
    source: Image.Image,
    key: tuple[int, int, int],
    border_width: int = 8,
) -> dict[str, Any]:
    rgb = np.asarray(source.convert("RGB"), dtype=np.float32)
    samples = border_pixels(rgb, border_width)
    key_array = np.asarray(key, dtype=np.float32).reshape(1, 3)
    distances = np.linalg.norm(samples - key_array, axis=1)
    percentiles = {
        "p50": float(np.percentile(distances, 50)),
        "p90": float(np.percentile(distances, 90)),
        "p95": float(np.percentile(distances, 95)),
        "p99": float(np.percentile(distances, 99)),
        "p99_5": float(np.percentile(distances, 99.5)),
        "max": float(np.max(distances)),
    }
    spread = percentiles["p99_5"] - percentiles["p50"]
    transparent = float(max(12, math.ceil(percentiles["p99_5"] + 4.0)))
    opaque = float(max(96, math.ceil(max(transparent + 48.0, transparent * 2.0))))
    opaque = min(255.0, opaque)
    if opaque <= transparent:
        opaque = transparent + 1.0

    if percentiles["p99_5"] <= 32.0 and spread <= 20.0 and percentiles["max"] <= 80.0:
        confidence = "high"
    elif percentiles["p99_5"] <= 96.0 and spread <= 56.0 and percentiles["max"] <= 160.0:
        confidence = "medium"
    else:
        confidence = "low"
    full_distance = np.linalg.norm(rgb - key_array.reshape(1, 1, 3), axis=2)
    margin_y = max(border_width * 2, int(round(rgb.shape[0] * 0.08)))
    margin_x = max(border_width * 2, int(round(rgb.shape[1] * 0.08)))
    if margin_y * 2 < rgb.shape[0] and margin_x * 2 < rgb.shape[1]:
        interior_distance = full_distance[margin_y:-margin_y, margin_x:-margin_x]
    else:
        interior_distance = full_distance
    transition_count = int(np.count_nonzero((interior_distance > transparent) & (interior_distance < opaque)))
    definite_foreground_count = int(np.count_nonzero(interior_distance >= opaque))
    transition_fraction = transition_count / max(1, interior_distance.size)
    transition_to_foreground_ratio = transition_count / max(1, definite_foreground_count)
    stable_core_support_ratio = definite_foreground_count / max(1, transition_count)
    near_key_subject_risk = bool(
        transition_fraction >= 0.01
        and transition_count >= 64
        # A hard-edged partial-opacity band is recoverable when it surrounds a
        # larger stable opaque core. Near-key subjects lack that supporting core
        # and remain dominated by ambiguous soft-matte pixels.
        and transition_to_foreground_ratio >= 1.0
    )
    auto_apply = confidence in {"high", "medium"} and transparent < 160.0 and not near_key_subject_risk
    issues: list[dict[str, Any]] = []
    if confidence == "medium":
        issues.append(
            {
                "severity": "warning",
                "code": "variable-chroma-border",
                "message": "Border chroma varies; adaptive thresholds are usable but require final residue QA.",
            }
        )
    if not auto_apply:
        issues.append(
            {
                "severity": "fail",
                "code": "unsafe-adaptive-thresholds",
                "message": "Border variation is too large for automatic threshold widening.",
            }
        )
    if near_key_subject_risk:
        issues.append(
            {
                "severity": "fail",
                "code": "near-key-subject-risk",
                "message": "A large interior region falls inside the soft matte band and may be damaged by chroma removal.",
            }
        )
    return {
        "schema_version": 1,
        "algorithm": "border-distance-percentile-recommendation",
        "chroma_key": format_hex(key),
        "border_width": border_width,
        "sample_count": int(distances.size),
        "distance_percentiles": {key: round(value, 4) for key, value in percentiles.items()},
        "distance_spread_p99_5_p50": round(spread, 4),
        "suggested_transparent_threshold": transparent,
        "suggested_opaque_threshold": opaque,
        "confidence": confidence,
        "interior_transition_pixels": transition_count,
        "interior_definite_foreground_pixels": definite_foreground_count,
        "interior_transition_fraction": round(transition_fraction, 6),
        "transition_to_foreground_ratio": round(transition_to_foreground_ratio, 6),
        "stable_core_support_ratio": round(stable_core_support_ratio, 6),
        "near_key_subject_risk": near_key_subject_risk,
        "auto_apply": auto_apply,
        "issues": issues,
    }


def remove_chroma(
    source: Image.Image,
    key: tuple[int, int, int],
    transparent_threshold: float = 12.0,
    opaque_threshold: float = 96.0,
    despill: bool = True,
) -> tuple[Image.Image, dict[str, Any]]:
    if transparent_threshold < 0:
        raise ValueError("transparent_threshold must be non-negative")
    if opaque_threshold <= transparent_threshold:
        raise ValueError("opaque_threshold must be greater than transparent_threshold")

    rgba = np.asarray(source.convert("RGBA"), dtype=np.float32)
    rgb = rgba[:, :, :3]
    original_alpha = rgba[:, :, 3] / 255.0
    key_array = np.asarray(key, dtype=np.float32).reshape(1, 1, 3)
    distance = np.linalg.norm(rgb - key_array, axis=2)
    source_spill_score = chroma_spill_score(rgb, key)

    matte = np.clip(
        (distance - transparent_threshold) / (opaque_threshold - transparent_threshold),
        0.0,
        1.0,
    )
    alpha = original_alpha * matte

    cleaned_rgb = rgb.copy()
    if despill:
        foreground_distances = distance[distance >= opaque_threshold]
        high_distance = float(np.percentile(foreground_distances, 99)) if foreground_distances.size else opaque_threshold
        seed_threshold = max(opaque_threshold + 48.0, opaque_threshold * 1.5, high_distance * 0.65)
        stable_foreground = (
            (distance >= seed_threshold)
            & (source_spill_score < 16.0)
            & (original_alpha >= 0.999)
        )
        # Large generated sheets frequently contain a 10-20px reflected chroma
        # band after model rendering and production upscaling. Search far enough
        # to reach a stable foreground seed without projecting into definite
        # interior pixels.
        radius = max(8, min(32, int(round(min(source.size) / 6.0))))
        mask_image = Image.fromarray((stable_foreground.astype(np.uint8) * 255), mode="L")
        blurred_mask = np.asarray(mask_image.filter(ImageFilter.BoxBlur(radius)), dtype=np.float32) / 255.0
        estimated_foreground = np.zeros_like(rgb)
        for channel in range(3):
            weighted = np.where(stable_foreground, rgb[:, :, channel], 0.0).astype(np.uint8)
            blurred = np.asarray(
                Image.fromarray(weighted, mode="L").filter(ImageFilter.BoxBlur(radius)),
                dtype=np.float32,
            )
            estimated_foreground[:, :, channel] = np.divide(
                blurred,
                blurred_mask,
                out=np.zeros_like(blurred),
                where=blurred_mask > 1.0 / 255.0,
            )
        foreground_vector = estimated_foreground - key_array
        source_vector = rgb - key_array
        denominator = np.sum(foreground_vector * foreground_vector, axis=2)
        projected_alpha = np.divide(
            np.sum(source_vector * foreground_vector, axis=2),
            denominator,
            out=matte.copy(),
            where=denominator > 1.0,
        )
        has_foreground_estimate = blurred_mask > 1.0 / 255.0
        transition_band = (matte > 0.0) & (matte < 1.0)
        projected_alpha = np.clip(projected_alpha, 0.0, 1.0)
        reconstructed = key_array + projected_alpha[:, :, None] * foreground_vector
        projection_fit_error = np.linalg.norm(rgb - reconstructed, axis=2)
        background_mask_image = Image.fromarray(
            ((distance <= transparent_threshold).astype(np.uint8) * 255),
            mode="L",
        )
        neighborhood_size = radius * 2 + 1
        near_background = np.asarray(
            background_mask_image.filter(ImageFilter.MaxFilter(neighborhood_size)),
            dtype=np.uint8,
        ) > 0
        fitted_chroma_mix = (
            near_background
            & (projected_alpha > 1.0 / 255.0)
            & (projected_alpha < 0.999)
            & (projection_fit_error <= 24.0)
        )
        spill_chroma_mix = (
            near_background
            & (source_spill_score >= 16.0)
            & (projected_alpha > 1.0 / 255.0)
        )
        projection_mask = has_foreground_estimate & (
            transition_band | fitted_chroma_mix | spill_chroma_mix
        )
        alpha = original_alpha * np.where(projection_mask, projected_alpha, matte)
        recoverable = projection_mask & (alpha > 1.0 / 255.0)
        cleaned_rgb[recoverable] = np.clip(estimated_foreground[recoverable], 0.0, 255.0)

    cleaned_distance = np.linalg.norm(cleaned_rgb - key_array, axis=2)
    cleaned_spill_score = chroma_spill_score(cleaned_rgb, key)
    opaque_chroma_spill = (
        near_background
        & (alpha >= 0.999)
        & (cleaned_spill_score >= 16.0)
    ) if despill else np.zeros(alpha.shape, dtype=bool)
    unresolved_chroma_edge = (
        (alpha > 1.0 / 255.0)
        & (
            (
                (alpha < 0.999)
                & (
                    (cleaned_distance <= opaque_threshold)
                    | (cleaned_spill_score >= 16.0)
                )
            )
            | opaque_chroma_spill
        )
    )
    alpha[unresolved_chroma_edge] = 0.0
    cleaned_rgb[unresolved_chroma_edge] = 0.0

    transparent = alpha <= 1.0 / 255.0
    cleaned_rgb[transparent] = 0.0
    output_array = np.empty_like(rgba, dtype=np.uint8)
    output_array[:, :, :3] = np.rint(np.clip(cleaned_rgb, 0.0, 255.0)).astype(np.uint8)
    output_array[:, :, 3] = np.rint(alpha * 255.0).astype(np.uint8)
    output = Image.fromarray(output_array, mode="RGBA")

    key_distance_after = np.linalg.norm(output_array[:, :, :3].astype(np.float32) - key_array, axis=2)
    visible = output_array[:, :, 3] > 0
    near_key_visible = visible & (key_distance_after <= transparent_threshold)
    report = {
        "schema_version": 1,
        "ok": int(np.count_nonzero(near_key_visible)) == 0,
        "algorithm": "adaptive-soft-matte-with-local-foreground-projection",
        "chroma_key": format_hex(key),
        "transparent_threshold": transparent_threshold,
        "opaque_threshold": opaque_threshold,
        "despill": despill,
        "width": output.width,
        "height": output.height,
        "transparent_pixels": int(np.count_nonzero(output_array[:, :, 3] == 0)),
        "partial_alpha_pixels": int(np.count_nonzero((output_array[:, :, 3] > 0) & (output_array[:, :, 3] < 255))),
        "opaque_pixels": int(np.count_nonzero(output_array[:, :, 3] == 255)),
        "visible_near_key_pixels": int(np.count_nonzero(near_key_visible)),
        "discarded_unresolved_chroma_edge_pixels": int(np.count_nonzero(unresolved_chroma_edge)),
        "discarded_opaque_chroma_spill_pixels": int(np.count_nonzero(opaque_chroma_spill)),
        "fitted_chroma_mix_pixels": int(np.count_nonzero(projection_mask & fitted_chroma_mix)) if despill else 0,
        "spill_chroma_mix_pixels": int(np.count_nonzero(projection_mask & spill_chroma_mix)) if despill else 0,
    }
    return output, report


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    key_group = parser.add_mutually_exclusive_group(required=True)
    key_group.add_argument("--chroma-key", type=parse_hex_color)
    key_group.add_argument("--auto-key-border", action="store_true")
    parser.add_argument("--border-width", type=int, default=8)
    parser.add_argument("--transparent-threshold", type=float, default=12.0)
    parser.add_argument("--opaque-threshold", type=float, default=96.0)
    parser.add_argument("--adaptive-thresholds", action="store_true")
    parser.add_argument("--no-despill", action="store_true")
    args = parser.parse_args()

    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"input image not found: {input_path}")
    with Image.open(input_path) as image:
        source = image.convert("RGBA")
    key = args.chroma_key
    if args.auto_key_border:
        key = sample_border_key(np.asarray(source.convert("RGB"), dtype=np.float32), args.border_width)
    assert key is not None

    diagnostics = recommend_chroma_thresholds(source, key, args.border_width)
    transparent_threshold = args.transparent_threshold
    opaque_threshold = args.opaque_threshold
    if args.adaptive_thresholds and diagnostics["auto_apply"]:
        transparent_threshold = float(diagnostics["suggested_transparent_threshold"])
        opaque_threshold = float(diagnostics["suggested_opaque_threshold"])

    output, report = remove_chroma(
        source,
        key,
        transparent_threshold=transparent_threshold,
        opaque_threshold=opaque_threshold,
        despill=not args.no_despill,
    )
    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.save(output_path, format="PNG")
    report.update(
        {
            "input": str(input_path),
            "output": str(output_path),
            "adaptive_thresholds_requested": args.adaptive_thresholds,
            "adaptive_thresholds_applied": bool(args.adaptive_thresholds and diagnostics["auto_apply"]),
            "threshold_diagnostics": diagnostics,
        }
    )
    if args.adaptive_thresholds and not diagnostics["auto_apply"]:
        report["ok"] = False
        report.setdefault("issues", []).extend(diagnostics["issues"])
    if args.json_out:
        write_json(args.json_out, report)
    print(json.dumps(report, ensure_ascii=False))
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
