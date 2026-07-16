#!/usr/bin/env python3
"""Prepare a multi-category UI asset run and split oversized categories into sheets."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from make_layout_guide import LayoutSpec, render_layout_guide, write_json
from prepare_ui_run import (
    CATEGORY_DEFAULTS,
    AssetRequest,
    build_alpha_matte_prompt,
    build_prompt,
    normalize_chroma_key,
    parse_pair,
    slugify,
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def pair(value: Any, fallback: list[int], label: str) -> list[int]:
    if value is None:
        return list(fallback)
    if isinstance(value, str):
        return parse_pair(value, label)
    if isinstance(value, list) and len(value) == 2 and all(isinstance(item, int) and item > 0 for item in value):
        return list(value)
    raise ValueError(f"{label} must be [positive, positive] or WIDTHxHEIGHT")


def copy_reference(source: Path, destination: Path) -> str:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"reference image not found: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination.name


def category_assets(category_spec: dict[str, Any]) -> list[dict[str, Any]]:
    raw_assets = category_spec.get("assets")
    if not isinstance(raw_assets, list) or not raw_assets:
        raise ValueError(f"category {category_spec.get('category')} requires a non-empty assets list")
    assets: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_assets, start=1):
        if isinstance(raw, str):
            asset = {"semantic_name": raw, "state": "Default", "description": ""}
        elif isinstance(raw, dict):
            asset = {
                "semantic_name": str(raw.get("semantic_name", "")).strip(),
                "state": str(raw.get("state", "Default")).strip() or "Default",
                "description": str(raw.get("description", "")).strip(),
            }
        else:
            raise ValueError("each asset must be a semantic-name string or object")
        if not asset["semantic_name"]:
            raise ValueError("asset semantic_name cannot be empty")
        asset["category_index"] = index
        assets.append(asset)
    return assets


def split_assets(assets: list[dict[str, Any]], capacity: int) -> list[list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for asset in assets:
        groups.setdefault(str(asset["semantic_name"]), []).append(asset)
    sheets: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for semantic_name, group in groups.items():
        if len(group) > capacity:
            raise ValueError(
                f"asset state group {semantic_name} contains {len(group)} variants and exceeds sheet capacity {capacity}"
            )
        if current and len(current) + len(group) > capacity:
            sheets.append(current)
            current = []
        current.extend(group)
    if current:
        sheets.append(current)
    return sheets


def prepare_batch(spec: dict[str, Any], run_dir: Path, force: bool = False) -> Path:
    project_id = slugify(str(spec.get("project_id", "game-ui")))
    categories = spec.get("categories")
    if not isinstance(categories, list) or not categories:
        raise ValueError("request requires a non-empty categories list")
    run_dir = run_dir.expanduser().resolve()
    if run_dir.exists() and any(run_dir.iterdir()) and not force:
        raise FileExistsError(f"output directory is not empty: {run_dir}; use --force to reuse it")

    for relative in (
        "references/layout-guides",
        "requests",
        "prompts",
        "generated",
        "extracted",
        "normalized",
        "final",
        "qa",
    ):
        (run_dir / relative).mkdir(parents=True, exist_ok=True)

    references: list[dict[str, str]] = []
    generation_method = str(spec.get("generation_method", "built-in-imagegen"))
    canonical = spec.get("canonical_style")
    if canonical:
        canonical_source = Path(str(canonical))
        name = copy_reference(
            canonical_source,
            run_dir / "references" / f"canonical-ui-style{canonical_source.suffix.lower()}",
        )
        references.append({"path": f"references/{name}", "role": "canonical-ui-style"})
    for index, value in enumerate(spec.get("references", []), start=1):
        source = Path(str(value))
        name = copy_reference(source, run_dir / "references" / f"reference-{index:02d}{source.suffix.lower()}")
        references.append({"path": f"references/{name}", "role": "supporting-style-reference"})

    jobs: list[dict[str, Any]] = []
    normalized_categories: list[dict[str, Any]] = []
    seen_categories: set[str] = set()
    for category_spec in categories:
        if not isinstance(category_spec, dict):
            raise ValueError("each category must be an object")
        category = str(category_spec.get("category", ""))
        if category not in CATEGORY_DEFAULTS:
            raise ValueError(f"unsupported category: {category}")
        if category in seen_categories:
            raise ValueError(f"duplicate category block: {category}")
        seen_categories.add(category)
        defaults = CATEGORY_DEFAULTS[category]
        assets = category_assets(category_spec)
        canvas = pair(category_spec.get("canvas"), defaults["canvas"], "canvas")
        grid = pair(category_spec.get("grid"), defaults["grid"], "grid")
        target_default = defaults["target_size"]
        target_size = None if category_spec.get("target_size") is None and target_default is None else pair(
            category_spec.get("target_size"), target_default, "target_size"
        )
        capacity = grid[0] * grid[1]
        transparency_mode = str(category_spec.get("transparency_mode", "chroma-key"))
        if transparency_mode not in {"chroma-key", "model-matte-derived", "native-alpha-required"}:
            raise ValueError(f"unsupported transparency_mode: {transparency_mode}")
        if transparency_mode == "native-alpha-required" and generation_method == "built-in-imagegen":
            raise ValueError("built-in-imagegen cannot prove native alpha; select an explicit native-alpha generation method")
        chroma_key = None if transparency_mode in {"native-alpha-required", "model-matte-derived"} else normalize_chroma_key(
            str(category_spec.get("chroma_key", "auto")), bool(category_spec.get("subject_uses_green", False))
        )
        category_request = {
            "category": category,
            "canvas": canvas,
            "grid": grid,
            "target_size": target_size,
            "alignment": str(category_spec.get("alignment", defaults["alignment"])),
            "padding": int(category_spec.get("padding", 8)),
            "chroma_key": chroma_key,
            "transparency_mode": transparency_mode,
            "generation_method": generation_method,
            "allow_attached_glow": bool(category_spec.get("allow_attached_glow", False)),
            "fragment_policy": category_spec.get("fragment_policy"),
            "assets": assets,
        }
        if category_request["fragment_policy"] is None:
            del category_request["fragment_policy"]
        normalized_categories.append(category_request)

        chunks = split_assets(assets, capacity)
        category_slug = category.lower().replace("_", "-")
        for sheet_number, chunk in enumerate(chunks, start=1):
            job_id = f"{category_slug}-sheet-{sheet_number:02d}"
            layout_spec = LayoutSpec(
                width=canvas[0],
                height=canvas[1],
                columns=grid[0],
                rows=grid[1],
                outer_margin=int(category_spec.get("outer_margin", 96)),
                gutter=int(category_spec.get("gutter", 48)),
                safe_padding=int(category_spec.get("safe_padding", 64)),
            )
            guide_path = run_dir / "references" / "layout-guides" / f"{job_id}.png"
            guide_json_path = guide_path.with_suffix(".json")
            write_json(guide_json_path, render_layout_guide(layout_spec, guide_path, f"{category} Sheet {sheet_number:02d}"))

            job_request = {
                "schema_version": 2,
                "project_id": project_id,
                "job_id": job_id,
                **{key: value for key, value in category_request.items() if key != "assets"},
                "assets": chunk,
            }
            request_path = run_dir / "requests" / f"{job_id}.json"
            write_json(request_path, job_request)
            prompt_path = run_dir / "prompts" / f"{job_id}.md"
            prompt_path.write_text(
                build_prompt(
                    category,
                    [AssetRequest(item["semantic_name"], item["state"], item["description"]) for item in chunk],
                    canvas[0],
                    canvas[1],
                    grid[0],
                    grid[1],
                    chroma_key,
                    str(spec.get("style_notes", "")),
                    category_request["allow_attached_glow"],
                    transparency_mode,
                ),
                encoding="utf-8",
            )
            matte_prompt_path = run_dir / "prompts" / f"{job_id}-alpha-matte.md"
            if transparency_mode == "model-matte-derived":
                matte_prompt_path.write_text(
                    build_alpha_matte_prompt(
                        category,
                        [AssetRequest(item["semantic_name"], item["state"], item["description"]) for item in chunk],
                        grid[0],
                        grid[1],
                    ),
                    encoding="utf-8",
                )
            jobs.append(
                {
                    "id": job_id,
                    "kind": "production-asset-sheet",
                    "category": category,
                    "sheet_number": sheet_number,
                    "status": "awaiting-generation",
                    "expected_count": len(chunk),
                    "request_file": f"requests/{job_id}.json",
                    "prompt_file": f"prompts/{job_id}.md",
                    "alpha_matte_prompt_file": f"prompts/{job_id}-alpha-matte.md"
                    if transparency_mode == "model-matte-derived" else None,
                    "layout_guide": f"references/layout-guides/{job_id}.png",
                    "layout_json": f"references/layout-guides/{job_id}.json",
                    "input_images": references
                    + [{"path": f"references/layout-guides/{job_id}.png", "role": "layout-guide-only"}],
                    "generated_output": f"generated/{job_id}.png",
                    "alpha_matte_output": f"generated/{job_id}-alpha-matte.png"
                    if transparency_mode == "model-matte-derived" else None,
                    "transparency_mode": transparency_mode,
                    "provenance_file": f"generated/{job_id}.provenance.json"
                    if transparency_mode == "native-alpha-required" else None,
                    "final_directory": f"final/{category}",
                }
            )

    created_at = datetime.now(timezone.utc).isoformat()
    write_json(
        run_dir / "request.json",
        {
            "schema_version": 2,
            "project_id": project_id,
            "created_at": created_at,
            "style_notes": str(spec.get("style_notes", "")),
            "generation_method": generation_method,
            "references": references,
            "categories": normalized_categories,
            "expected_count": sum(len(item["assets"]) for item in normalized_categories),
        },
    )
    write_json(run_dir / "jobs.json", {"schema_version": 2, "created_at": created_at, "jobs": jobs})
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path, help="Batch request JSON")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run_dir = prepare_batch(read_json(args.request), args.output_dir, force=args.force)
    jobs = read_json(run_dir / "jobs.json")["jobs"]
    print(json.dumps({"ok": True, "run_dir": str(run_dir), "job_count": len(jobs)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
