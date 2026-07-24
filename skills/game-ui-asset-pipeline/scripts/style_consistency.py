#!/usr/bin/env python3
"""Measure canonical and cross-sheet visual style consistency for UI assets."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def image_profile(image: Image.Image, minimum_alpha: int = 16) -> dict[str, Any]:
    rgba = image.convert("RGBA")
    rgba.thumbnail((128, 128), Image.Resampling.LANCZOS)
    array = np.asarray(rgba, dtype=np.uint8)
    visible = array[:, :, 3] >= minimum_alpha
    rgb = array[:, :, :3][visible]
    if rgb.size == 0:
        raise ValueError("style-profile-empty-visible-pixels")

    quantized = np.clip(rgb // 64, 0, 3)
    bins = quantized[:, 0] * 16 + quantized[:, 1] * 4 + quantized[:, 2]
    histogram = np.bincount(bins, minlength=64).astype(np.float64)
    histogram /= max(1.0, float(histogram.sum()))

    rgb_float = rgb.astype(np.float32)
    maximum = rgb_float.max(axis=1)
    minimum = rgb_float.min(axis=1)
    saturation = np.divide(
        maximum - minimum,
        np.maximum(maximum, 1.0),
        out=np.zeros_like(maximum),
        where=maximum > 0,
    )
    luminance = 0.2126 * rgb_float[:, 0] + 0.7152 * rgb_float[:, 1] + 0.0722 * rgb_float[:, 2]

    gray = np.asarray(rgba.convert("L"), dtype=np.float32)
    alpha = array[:, :, 3]
    horizontal_mask = (alpha[:, 1:] >= minimum_alpha) & (alpha[:, :-1] >= minimum_alpha)
    vertical_mask = (alpha[1:, :] >= minimum_alpha) & (alpha[:-1, :] >= minimum_alpha)
    edge_values = []
    if np.any(horizontal_mask):
        edge_values.append(np.abs(gray[:, 1:] - gray[:, :-1])[horizontal_mask])
    if np.any(vertical_mask):
        edge_values.append(np.abs(gray[1:, :] - gray[:-1, :])[vertical_mask])
    edge_density = float(np.mean(np.concatenate(edge_values)) / 255.0) if edge_values else 0.0
    return {
        "histogram": histogram.tolist(),
        "mean_rgb": (np.mean(rgb_float, axis=0) / 255.0).tolist(),
        "mean_luminance": float(np.mean(luminance) / 255.0),
        "mean_saturation": float(np.mean(saturation)),
        "edge_density": edge_density,
        "visible_pixels": int(rgb.shape[0]),
    }


def aggregate_profiles(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    if not profiles:
        raise ValueError("style-profile-requires-images")
    weights = np.asarray([max(1, int(profile["visible_pixels"])) for profile in profiles], dtype=np.float64)
    weights /= weights.sum()
    histogram = sum(
        np.asarray(profile["histogram"], dtype=np.float64) * weight
        for profile, weight in zip(profiles, weights)
    )
    return {
        "histogram": histogram.tolist(),
        "mean_rgb": np.sum(
            np.asarray([profile["mean_rgb"] for profile in profiles], dtype=np.float64) * weights[:, None],
            axis=0,
        ).tolist(),
        "mean_luminance": float(sum(profile["mean_luminance"] * weight for profile, weight in zip(profiles, weights))),
        "mean_saturation": float(sum(profile["mean_saturation"] * weight for profile, weight in zip(profiles, weights))),
        "edge_density": float(sum(profile["edge_density"] * weight for profile, weight in zip(profiles, weights))),
        "visible_pixels": int(sum(int(profile["visible_pixels"]) for profile in profiles)),
        "image_count": len(profiles),
    }


def profile_similarity(first: dict[str, Any], second: dict[str, Any]) -> dict[str, float]:
    first_hist = np.asarray(first["histogram"], dtype=np.float64)
    second_hist = np.asarray(second["histogram"], dtype=np.float64)
    palette = float(np.minimum(first_hist, second_hist).sum())
    mean_color_distance = float(
        np.linalg.norm(np.asarray(first["mean_rgb"], dtype=np.float64) - np.asarray(second["mean_rgb"], dtype=np.float64))
        / np.sqrt(3.0)
    )
    mean_color = max(0.0, 1.0 - mean_color_distance)
    luminance = max(0.0, 1.0 - abs(float(first["mean_luminance"]) - float(second["mean_luminance"])))
    saturation = max(0.0, 1.0 - abs(float(first["mean_saturation"]) - float(second["mean_saturation"])))
    edge_scale = max(float(first["edge_density"]), float(second["edge_density"]), 0.05)
    edge = max(0.0, 1.0 - abs(float(first["edge_density"]) - float(second["edge_density"])) / edge_scale)
    score = 100.0 * (0.35 * palette + 0.20 * mean_color + 0.20 * luminance + 0.15 * saturation + 0.10 * edge)
    return {
        "score": round(score, 2),
        "palette": round(100.0 * palette, 2),
        "mean_color": round(100.0 * mean_color, 2),
        "luminance": round(100.0 * luminance, 2),
        "saturation": round(100.0 * saturation, 2),
        "edge": round(100.0 * edge, 2),
    }


def evaluate_style_consistency(
    manifest: dict[str, Any],
    run_dir: Path,
    canonical_path: Path,
    warning_below: float = 60.0,
    fail_below: float = 40.0,
) -> dict[str, Any]:
    if not 0 <= fail_below <= warning_below <= 100:
        raise ValueError("style consistency thresholds must satisfy 0 <= fail <= warning <= 100")
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for entry in manifest.get("assets", []):
        job_id = str(entry.get("job_id", ""))
        output = entry.get("output")
        if job_id and output:
            grouped[job_id].append(
                {
                    "path": str(run_dir / str(output)),
                    "output": str(output),
                    "asset_id": str(entry.get("id", "")),
                }
            )
    if len(grouped) < 2:
        return {
            "schema_version": 1,
            "ok": True,
            "evaluated": False,
            "reason": "cross-sheet scoring requires at least two jobs",
            "issues": [],
            "jobs": [],
            "pairs": [],
        }

    with Image.open(canonical_path) as canonical_image:
        canonical_profile = image_profile(canonical_image, minimum_alpha=1)
    job_profiles: dict[str, dict[str, Any]] = {}
    profile_issues: list[dict[str, Any]] = []
    for job_id, entries in sorted(grouped.items()):
        profiles = []
        for entry in entries:
            path = Path(entry["path"])
            with Image.open(path) as image:
                try:
                    profiles.append(image_profile(image))
                except ValueError as error:
                    if str(error) != "style-profile-empty-visible-pixels":
                        raise
                    profile_issues.append(
                        {
                            "severity": "fail",
                            "code": "style-profile-empty-visible-pixels",
                            "job_id": job_id,
                            "asset_id": entry["asset_id"],
                            "file": entry["output"],
                        }
                    )
        if profiles:
            job_profiles[job_id] = aggregate_profiles(profiles)

    if len(job_profiles) < 2:
        return {
            "schema_version": 1,
            "ok": not profile_issues,
            "evaluated": False,
            "reason": "cross-sheet scoring requires at least two jobs with visible profiles",
            "issues": profile_issues,
            "jobs": [],
            "pairs": [],
        }

    pairs = []
    pair_scores: dict[str, list[float]] = defaultdict(list)
    job_ids = sorted(job_profiles)
    for index, first_id in enumerate(job_ids):
        for second_id in job_ids[index + 1 :]:
            similarity = profile_similarity(job_profiles[first_id], job_profiles[second_id])
            pairs.append({"first_job": first_id, "second_job": second_id, **similarity})
            pair_scores[first_id].append(similarity["score"])
            pair_scores[second_id].append(similarity["score"])

    jobs = []
    issues = list(profile_issues)
    for job_id in job_ids:
        canonical = profile_similarity(job_profiles[job_id], canonical_profile)
        cross_sheet = round(float(np.mean(pair_scores[job_id])), 2) if pair_scores[job_id] else canonical["score"]
        combined = round(0.45 * canonical["score"] + 0.55 * cross_sheet, 2)
        severity = None
        if combined < fail_below:
            severity = "fail"
        elif combined < warning_below:
            severity = "warning"
        job_result = {
            "id": job_id,
            "score": combined,
            "canonical_similarity": canonical,
            "cross_sheet_similarity": cross_sheet,
            "profile": {
                key: round(float(value), 6)
                for key, value in job_profiles[job_id].items()
                if key not in {"histogram", "mean_rgb"}
            },
            "severity": severity or "pass",
        }
        jobs.append(job_result)
        if severity:
            issues.append(
                {
                    "severity": severity,
                    "code": "cross-sheet-style-drift",
                    "job_id": job_id,
                    "style_score": combined,
                    "warning_below": warning_below,
                    "fail_below": fail_below,
                    "canonical_similarity": canonical["score"],
                    "cross_sheet_similarity": cross_sheet,
                }
            )
    return {
        "schema_version": 1,
        "ok": not any(issue["severity"] == "fail" for issue in issues),
        "evaluated": True,
        "canonical": canonical_path.name,
        "overall_score": round(float(np.mean([job["score"] for job in jobs])), 2),
        "warning_below": warning_below,
        "fail_below": fail_below,
        "jobs": jobs,
        "pairs": pairs,
        "issues": issues,
        "method": "visible-RGBA palette histogram + mean RGB distance + luminance + saturation + edge density",
    }
