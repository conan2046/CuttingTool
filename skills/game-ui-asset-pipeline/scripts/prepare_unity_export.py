#!/usr/bin/env python3
"""Prepare Unity sprite import, 9-slice, and interactive prefab generation inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image

from infer_nine_slice import infer_nine_slice


SUPPORTED_UNITY_MAJOR = "2022.3"
UNITY_CANVAS_REFERENCE_PPU = 100.0


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_unity_project(project: Path) -> str:
    project = project.expanduser().resolve()
    version_file = project / "ProjectSettings" / "ProjectVersion.txt"
    assets = project / "Assets"
    packages = project / "Packages"
    if not version_file.is_file() or not assets.is_dir() or not packages.is_dir():
        raise ValueError(f"not a Unity project: {project}")
    first_line = version_file.read_text(encoding="utf-8").splitlines()[0]
    version = first_line.split(":", 1)[-1].strip()
    if not version.startswith(SUPPORTED_UNITY_MAJOR):
        raise ValueError(f"unsupported Unity version {version}; expected {SUPPORTED_UNITY_MAJOR}.x")
    return version


def validate_asset_path(value: str) -> str:
    normalized = value.replace("\\", "/").strip("/")
    if not normalized.startswith("Assets/") or ".." in normalized.split("/"):
        raise ValueError(f"Unity asset path must stay under Assets/: {value}")
    return normalized


def install_embedded_package(unity_project: Path, package_source: Path) -> str:
    package_source = package_source.expanduser().resolve()
    destination = unity_project / "Packages" / "com.hongda.game-ui-asset-pipeline"
    if not (package_source / "package.json").is_file():
        raise FileNotFoundError(f"Unity package source is incomplete: {package_source}")
    if destination.exists():
        for source in sorted(package_source.rglob("*")):
            if source.is_file():
                relative = source.relative_to(package_source)
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    else:
        shutil.copytree(package_source, destination)
    return destination.relative_to(unity_project).as_posix()


def collect_layout_target_sizes(screens: list[dict[str, Any]]) -> dict[str, list[list[float]]]:
    targets: dict[str, list[list[float]]] = {}
    for screen in screens:
        for element in screen["elements"]:
            size = [float(element["size"][0]), float(element["size"][1])]
            for field in (
                "asset_id",
                "highlighted_asset_id",
                "pressed_asset_id",
                "disabled_asset_id",
            ):
                asset_id = element[field]
                if asset_id:
                    targets.setdefault(asset_id, []).append(size)
    return targets


def derive_pixels_per_unit(
    source_size: tuple[int, int],
    target_sizes: list[list[float]],
    default_ppu: float,
) -> tuple[float, float | None]:
    source_width, source_height = source_size
    if source_width <= 0 or source_height <= 0 or default_ppu <= 0:
        raise ValueError("source dimensions and default pixels_per_unit must be positive")
    if not target_sizes:
        return float(default_ppu), None
    scales = [
        min(float(size[0]) / source_width, float(size[1]) / source_height)
        for size in target_sizes
        if float(size[0]) > 0 and float(size[1]) > 0
    ]
    if not scales:
        return float(default_ppu), None
    minimum_scale = min(scales)
    derived = max(float(default_ppu), UNITY_CANVAS_REFERENCE_PPU / minimum_scale)
    return round(derived, 4), round(minimum_scale, 6)


def validate_sliced_layout_geometry(
    asset_id: str,
    border: list[int],
    ppu: float,
    target_sizes: list[list[float]],
) -> list[dict[str, Any]]:
    if not any(border) or not target_sizes:
        return []
    horizontal_units = (border[0] + border[2]) * UNITY_CANVAS_REFERENCE_PPU / ppu
    vertical_units = (border[1] + border[3]) * UNITY_CANVAS_REFERENCE_PPU / ppu
    issues: list[dict[str, Any]] = []
    for target_index, size in enumerate(target_sizes):
        if horizontal_units >= float(size[0]) or vertical_units >= float(size[1]):
            issues.append(
                {
                    "severity": "fail",
                    "code": "nine-slice-border-exceeds-layout-size",
                    "asset_id": asset_id,
                    "target_index": target_index,
                    "target_size": size,
                    "border_units": [round(horizontal_units, 4), round(vertical_units, 4)],
                    "pixels_per_unit": ppu,
                }
            )
    return issues


def normalize_layout(layout: dict[str, Any] | None) -> list[dict[str, Any]]:
    if layout is None:
        return []
    schema_version = layout.get("schema_version")
    if schema_version not in {1, 2}:
        raise ValueError("unity layout schema_version must be 1 or 2")
    screens = layout.get("screens")
    if not isinstance(screens, list) or not screens:
        raise ValueError("unity layout requires at least one screen")
    normalized: list[dict[str, Any]] = []
    for screen_index, screen in enumerate(screens):
        reference_size = screen.get("reference_size")
        if not isinstance(reference_size, list) or len(reference_size) != 2:
            raise ValueError(f"screens[{screen_index}].reference_size must be [width,height]")
        elements = screen.get("elements")
        if not isinstance(elements, list) or not elements:
            raise ValueError(f"screens[{screen_index}].elements requires at least one element")
        ids: set[str] = set()
        normalized_elements = []
        for element_index, element in enumerate(elements):
            element_id = str(element.get("id", "")).strip()
            if not element_id or element_id in ids:
                raise ValueError(f"invalid duplicate element id at screens[{screen_index}].elements[{element_index}]")
            ids.add(element_id)
            kind = str(element.get("kind", "Image"))
            if kind not in {"Image", "Button", "HorizontalLayoutGroup", "VerticalLayoutGroup"}:
                raise ValueError(f"unsupported Unity element kind: {kind}")
            is_layout_group = kind in {"HorizontalLayoutGroup", "VerticalLayoutGroup"}
            if is_layout_group and schema_version < 2:
                raise ValueError(f"{kind} requires unity layout schema_version 2")
            parent_id = str(element.get("parent_id", ""))
            if parent_id and parent_id not in ids:
                raise ValueError(
                    f"parent_id must reference an earlier element at screens[{screen_index}].elements[{element_index}]"
                )
            vectors = {
                "anchor_min": element.get("anchor_min", [0.5, 0.5]),
                "anchor_max": element.get("anchor_max", [0.5, 0.5]),
                "pivot": element.get("pivot", [0.5, 0.5]),
                "anchored_position": element.get("anchored_position", [0.0, 0.0]),
                "size": element.get("size", [100.0, 100.0]),
            }
            for vector_name, vector in vectors.items():
                if not isinstance(vector, list) or len(vector) != 2 or not all(isinstance(value, (int, float)) for value in vector):
                    raise ValueError(
                        f"screens[{screen_index}].elements[{element_index}].{vector_name} must contain two numbers"
                    )
            if vectors["size"][0] <= 0 or vectors["size"][1] <= 0:
                raise ValueError(f"screens[{screen_index}].elements[{element_index}].size must be positive")
            color = element.get("color", [1.0, 1.0, 1.0, 1.0])
            if not isinstance(color, list) or len(color) != 4 or not all(isinstance(value, (int, float)) for value in color):
                raise ValueError(f"screens[{screen_index}].elements[{element_index}].color must contain four numbers")
            if not all(0.0 <= float(value) <= 1.0 for value in color):
                raise ValueError(f"screens[{screen_index}].elements[{element_index}].color values must be between 0 and 1")
            spacing = element.get("spacing", 0.0)
            if not isinstance(spacing, (int, float)):
                raise ValueError(f"screens[{screen_index}].elements[{element_index}].spacing must be a number")
            padding = element.get("padding", [0, 0, 0, 0])
            if (
                not isinstance(padding, list)
                or len(padding) != 4
                or not all(isinstance(value, int) and value >= 0 for value in padding)
            ):
                raise ValueError(
                    f"screens[{screen_index}].elements[{element_index}].padding must be [left,right,top,bottom] non-negative integers"
                )
            child_alignment = str(element.get("child_alignment", "MiddleCenter"))
            supported_alignments = {
                "UpperLeft", "UpperCenter", "UpperRight",
                "MiddleLeft", "MiddleCenter", "MiddleRight",
                "LowerLeft", "LowerCenter", "LowerRight",
            }
            if child_alignment not in supported_alignments:
                raise ValueError(
                    f"screens[{screen_index}].elements[{element_index}].child_alignment is unsupported: {child_alignment}"
                )
            asset_fields = (
                str(element.get("asset_id", "")),
                str(element.get("highlighted_asset_id", "")),
                str(element.get("pressed_asset_id", "")),
                str(element.get("disabled_asset_id", "")),
            )
            if is_layout_group and any(asset_fields):
                raise ValueError(f"{kind} cannot reference sprites at screens[{screen_index}].elements[{element_index}]")
            normalized_elements.append(
                {
                    "id": element_id,
                    "parent_id": parent_id,
                    "asset_id": str(element.get("asset_id", "")),
                    "kind": kind,
                    "anchor_min": list(vectors["anchor_min"]),
                    "anchor_max": list(vectors["anchor_max"]),
                    "pivot": list(vectors["pivot"]),
                    "anchored_position": list(vectors["anchored_position"]),
                    "size": list(vectors["size"]),
                    "color": [float(value) for value in color],
                    "preserve_aspect": bool(element.get("preserve_aspect", False)),
                    "raycast_target": bool(element.get("raycast_target", kind == "Button")),
                    "highlighted_asset_id": str(element.get("highlighted_asset_id", "")),
                    "pressed_asset_id": str(element.get("pressed_asset_id", "")),
                    "disabled_asset_id": str(element.get("disabled_asset_id", "")),
                    "spacing": float(spacing),
                    "padding": list(padding),
                    "child_alignment": child_alignment,
                    "control_child_size": bool(element.get("control_child_size", False)),
                    "child_force_expand": bool(element.get("child_force_expand", False)),
                }
            )
        direct_child_counts = {
            element["id"]: sum(1 for child in normalized_elements if child["parent_id"] == element["id"])
            for element in normalized_elements
            if element["kind"] in {"HorizontalLayoutGroup", "VerticalLayoutGroup"}
        }
        for group_id, child_count in direct_child_counts.items():
            if child_count < 2:
                raise ValueError(f"layout group {group_id} requires at least two direct children")
        normalized.append(
            {
                "id": str(screen.get("id", f"screen-{screen_index + 1:02d}")),
                "name": str(screen.get("name", screen.get("id", f"Screen{screen_index + 1}"))),
                "reference_size": list(reference_size),
                "elements": normalized_elements,
            }
        )
    return normalized


def prepare_unity_export(
    run_dir: Path,
    unity_project: Path,
    package_source: Path,
    layout_path: Path | None = None,
    import_root: str = "Assets/_Generated/GameUI",
    pixels_per_unit: float = 100.0,
    nine_slice_confidence: float = 0.65,
) -> dict[str, Any]:
    run_dir = run_dir.expanduser().resolve()
    unity_project = unity_project.expanduser().resolve()
    unity_version = validate_unity_project(unity_project)
    manifest_path = run_dir / "final" / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"formal Manifest not found: {manifest_path}")
    manifest = read_json(manifest_path)
    qa_report_path = run_dir / "qa" / "qa-report.json"
    if not qa_report_path.is_file():
        raise FileNotFoundError(f"formal QA report not found: {qa_report_path}")
    qa_report = read_json(qa_report_path)
    if not qa_report.get("ok") or int(qa_report.get("fail_count", 0)) != 0:
        raise ValueError(f"formal QA has unresolved failures: {qa_report_path}")
    project_id = str(manifest.get("project_id", "game-ui"))
    import_root = validate_asset_path(import_root)
    generated_root = f"{import_root}/{project_id}"
    sprite_root = f"{generated_root}/Sprites"
    prefab_root = f"{generated_root}/Prefabs"
    layout = read_json(layout_path) if layout_path else None
    screens = normalize_layout(layout)
    overrides = dict((layout or {}).get("nine_slice_overrides", {}))
    ppu_overrides = dict((layout or {}).get("pixels_per_unit_overrides", {}))
    for asset_id, value in ppu_overrides.items():
        if not isinstance(value, (int, float)) or float(value) <= 0:
            raise ValueError(f"invalid pixels_per_unit_overrides value for {asset_id}")
    layout_target_sizes = collect_layout_target_sizes(screens)
    sprites: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    created_files: list[str] = []
    asset_ids: set[str] = set()
    for entry in manifest.get("assets", []):
        asset_id = str(entry["id"])
        if asset_id in asset_ids:
            raise ValueError(f"duplicate Manifest asset id: {asset_id}")
        asset_ids.add(asset_id)
        source = (run_dir / str(entry["output"])).resolve()
        try:
            source.relative_to(run_dir)
        except ValueError as error:
            raise ValueError(f"Manifest output escapes run directory: {entry['output']}") from error
        if not source.is_file():
            raise FileNotFoundError(f"Manifest output missing: {source}")
        destination_asset = f"{sprite_root}/{Path(str(entry['output'])).name}"

        category = str(entry["category"])
        with Image.open(source) as image:
            source_width, source_height = image.size
        asset_target_sizes = layout_target_sizes.get(asset_id, [])
        derived_ppu, layout_scale = derive_pixels_per_unit(
            (source_width, source_height),
            asset_target_sizes if category in {"Panel", "Button"} else [],
            pixels_per_unit,
        )
        if asset_id in ppu_overrides:
            resolved_ppu = float(ppu_overrides[asset_id])
            ppu_origin = "manual-override"
        elif layout_scale is not None:
            resolved_ppu = derived_ppu
            ppu_origin = "layout-derived"
        else:
            resolved_ppu = float(pixels_per_unit)
            ppu_origin = "default"
        border = [0, 0, 0, 0]
        border_origin = "not-applicable"
        confidence = 1.0
        if category in {"Panel", "Button"}:
            override = overrides.get(asset_id)
            if override is not None:
                if not isinstance(override, list) or len(override) != 4 or not all(isinstance(value, int) and value >= 0 for value in override):
                    raise ValueError(f"invalid nine_slice_overrides value for {asset_id}")
                border = list(override)
                if border[0] + border[2] >= source_width or border[1] + border[3] >= source_height:
                    raise ValueError(f"nine_slice_overrides leaves no stretchable center for {asset_id}")
                border_origin = "manual-override"
            else:
                with Image.open(source) as image:
                    inferred = infer_nine_slice(image, minimum_confidence=nine_slice_confidence)
                confidence = float(inferred["confidence"])
                if inferred["apply"]:
                    border = list(inferred["border"])
                    border_origin = "auto-inferred"
                else:
                    border_origin = "blocked-low-confidence"
                    issues.append(
                        {
                            "severity": "fail",
                            "code": "nine-slice-manual-override-required",
                            "asset_id": asset_id,
                            "confidence": confidence,
                        }
                    )
        issues.extend(validate_sliced_layout_geometry(asset_id, border, resolved_ppu, asset_target_sizes))
        sprites.append(
            {
                "id": asset_id,
                "category": category,
                "source_sha256": sha256(source),
                "asset_path": destination_asset,
                "pixels_per_unit": resolved_ppu,
                "pixels_per_unit_origin": ppu_origin,
                "layout_scale": layout_scale,
                "layout_target_sizes": asset_target_sizes,
                "border": border,
                "border_origin": border_origin,
                "border_confidence": confidence,
                "pivot": list(entry.get("pivot", [0.5, 0.5])),
            }
        )

    referenced_asset_ids = {
        asset_id
        for screen in screens
        for element in screen["elements"]
        for asset_id in (
            element["asset_id"],
            element["highlighted_asset_id"],
            element["pressed_asset_id"],
            element["disabled_asset_id"],
        )
        if asset_id
    }
    missing_ids = sorted(referenced_asset_ids - asset_ids)
    if missing_ids:
        raise ValueError(f"Unity layout references unknown asset ids: {', '.join(missing_ids)}")

    preflight_ok = not any(issue["severity"] == "fail" for issue in issues)
    package_path = "Packages/com.hongda.game-ui-asset-pipeline"
    if preflight_ok:
        package_path = install_embedded_package(unity_project, package_source)
        for sprite in sprites:
            destination = unity_project / sprite["asset_path"]
            source_entry = next(entry for entry in manifest.get("assets", []) if str(entry["id"]) == sprite["id"])
            source = (run_dir / str(source_entry["output"])).resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            created_files.append(sprite["asset_path"])

    unity_dir = run_dir / "unity"
    report_path = unity_dir / "unity-import-report.json"
    plan_path = unity_dir / "unity-import-plan.json"
    plan = {
        "schema_version": 2,
        "layout_schema_version": int((layout or {}).get("schema_version", 1)),
        "project_id": project_id,
        "unity_version": unity_version,
        "generated_root": generated_root,
        "prefab_root": prefab_root,
        "report_path": str(report_path),
        "preview_output_dir": str(unity_dir / "previews"),
        "create_asset_prefabs": True,
        "sprites": sprites,
        "screens": screens,
    }
    write_json(plan_path, plan)
    rollback = {
        "schema_version": 1,
        "unity_project": str(unity_project),
        "generated_root": generated_root,
        "embedded_package": package_path,
        "created_files": created_files,
    }
    write_json(unity_dir / "unity-rollback.json", rollback)
    preflight = {
        "schema_version": 1,
        "ok": preflight_ok,
        "project_id": project_id,
        "unity_project": str(unity_project),
        "unity_version": unity_version,
        "sprite_count": len(sprites),
        "screen_count": len(screens),
        "layout_schema_version": int((layout or {}).get("schema_version", 1)),
        "qa_report": str(qa_report_path),
        "issues": issues,
        "plan": str(plan_path),
    }
    write_json(unity_dir / "unity-preflight.json", preflight)
    return preflight


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--unity-project", required=True, type=Path)
    parser.add_argument("--layout", type=Path)
    parser.add_argument("--package-source", type=Path, default=Path(__file__).resolve().parents[1] / "assets" / "unity-package")
    parser.add_argument("--import-root", default="Assets/_Generated/GameUI")
    parser.add_argument("--pixels-per-unit", type=float, default=100.0)
    parser.add_argument("--nine-slice-confidence", type=float, default=0.65)
    args = parser.parse_args()
    try:
        result = prepare_unity_export(
            args.run_dir,
            args.unity_project,
            args.package_source,
            args.layout,
            args.import_root,
            args.pixels_per_unit,
            args.nine_slice_confidence,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
