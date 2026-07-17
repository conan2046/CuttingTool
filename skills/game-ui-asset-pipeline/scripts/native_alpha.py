#!/usr/bin/env python3
"""Validate and fingerprint model-native RGBA sources before asset extraction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


REQUIRED_TRANSPARENCY_MODE = "native-alpha-required"
REQUIRED_ALPHA_ORIGIN = "model-native"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.expanduser().resolve().open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def alpha_statistics(image: Image.Image) -> dict[str, Any]:
    has_alpha = "A" in image.getbands()
    if not has_alpha:
        return {
            "has_alpha": False,
            "mode": image.mode,
            "width": image.width,
            "height": image.height,
            "alpha_min": None,
            "alpha_max": None,
            "distinct_alpha_levels": 0,
            "transparent_pixels": 0,
            "partial_alpha_pixels": 0,
            "opaque_pixels": image.width * image.height,
            "partial_alpha_ratio": 0.0,
        }
    alpha = np.asarray(image.getchannel("A"), dtype=np.uint8)
    partial = (alpha > 0) & (alpha < 255)
    return {
        "has_alpha": True,
        "mode": image.mode,
        "width": image.width,
        "height": image.height,
        "alpha_min": int(alpha.min()),
        "alpha_max": int(alpha.max()),
        "distinct_alpha_levels": int(np.unique(alpha).size),
        "transparent_pixels": int(np.count_nonzero(alpha == 0)),
        "partial_alpha_pixels": int(np.count_nonzero(partial)),
        "opaque_pixels": int(np.count_nonzero(alpha == 255)),
        "partial_alpha_ratio": float(np.count_nonzero(partial) / alpha.size),
    }


def validate_native_alpha_source(
    source_path: Path,
    provenance_path: Path,
    expected_source_output: str,
    minimum_distinct_alpha_levels: int = 8,
    minimum_partial_alpha_pixels: int = 32,
) -> dict[str, Any]:
    source_path = source_path.expanduser().resolve()
    provenance_path = provenance_path.expanduser().resolve()
    issues: list[dict[str, Any]] = []
    if not provenance_path.is_file():
        return {
            "schema_version": 1,
            "ok": False,
            "source": expected_source_output,
            "provenance": str(provenance_path),
            "issues": [{"severity": "fail", "code": "missing-native-alpha-provenance"}],
        }
    provenance = read_json(provenance_path)
    actual_sha256 = sha256_file(source_path)
    generation_method = str(provenance.get("generation_method", "")).strip()
    checks = (
        (provenance.get("schema_version") == 1, "unsupported-native-alpha-provenance-schema"),
        (provenance.get("transparency_mode") == REQUIRED_TRANSPARENCY_MODE, "invalid-transparency-mode"),
        (provenance.get("alpha_origin") == REQUIRED_ALPHA_ORIGIN, "unproven-native-alpha-origin"),
        (provenance.get("background_removal_applied") is False, "background-removal-not-native-alpha"),
        (provenance.get("source_output") == expected_source_output, "provenance-source-path-mismatch"),
        (provenance.get("source_sha256") == actual_sha256, "provenance-source-hash-mismatch"),
        (bool(str(provenance.get("model", "")).strip()), "missing-generation-model"),
        (bool(generation_method), "missing-generation-method"),
        (not generation_method.lower().startswith("built-in-imagegen"), "built-in-imagegen-not-native-alpha"),
    )
    for passed, code in checks:
        if not passed:
            issues.append({"severity": "fail", "code": code})

    with Image.open(source_path) as opened:
        stats = alpha_statistics(opened)
    if not stats["has_alpha"]:
        issues.append({"severity": "fail", "code": "source-has-no-alpha-channel"})
    else:
        if stats["transparent_pixels"] == 0:
            issues.append({"severity": "fail", "code": "source-has-no-transparent-pixels"})
        if stats["partial_alpha_pixels"] < minimum_partial_alpha_pixels:
            issues.append(
                {
                    "severity": "fail",
                    "code": "insufficient-partial-alpha-pixels",
                    "minimum": minimum_partial_alpha_pixels,
                    "actual": stats["partial_alpha_pixels"],
                }
            )
        if stats["distinct_alpha_levels"] < minimum_distinct_alpha_levels:
            issues.append(
                {
                    "severity": "fail",
                    "code": "insufficient-alpha-levels",
                    "minimum": minimum_distinct_alpha_levels,
                    "actual": stats["distinct_alpha_levels"],
                }
            )
    return {
        "schema_version": 1,
        "ok": not issues,
        "source": expected_source_output,
        "source_sha256": actual_sha256,
        "provenance_file": str(provenance_path),
        "provenance": provenance,
        "alpha": stats,
        "issues": issues,
    }
