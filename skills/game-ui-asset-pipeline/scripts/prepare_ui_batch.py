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
from prepare_unity_export import normalize_layout


CHROMA_CANDIDATES = [
    ("#00FF00", "green"),
    ("#FF00FF", "magenta"),
    ("#00FFFF", "cyan"),
]
COLOR_TERMS = {
    "green": ("green", "emerald", "jade", "lime", "绿色", "翠绿", "翡翠", "青绿"),
    "magenta": ("magenta", "fuchsia", "purple", "violet", "品红", "紫色", "紫红", "洋红"),
    "cyan": ("cyan", "aqua", "turquoise", "青色", "蓝绿", "湖蓝"),
}
RISK_PRIORITY = {
    "Panel": 0,
    "Button": 1,
    "Icon_Status": 2,
}


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


def category_assets(category_spec: dict[str, Any], category: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    raw_assets = category_spec.get("assets")
    if not isinstance(raw_assets, list) or not raw_assets:
        raise ValueError(f"category {category_spec.get('category')} requires a non-empty assets list")
    assets: list[dict[str, Any]] = []
    panel_by_frame_style: dict[str, dict[str, Any]] = {}
    panel_aliases: list[dict[str, str]] = []
    for index, raw in enumerate(raw_assets, start=1):
        if isinstance(raw, str):
            asset = {"semantic_name": raw, "state": "Default", "description": ""}
        elif isinstance(raw, dict):
            asset = {
                "semantic_name": str(raw.get("semantic_name", "")).strip(),
                "state": str(raw.get("state", "Default")).strip() or "Default",
                "description": str(raw.get("description", "")).strip(),
            }
            if category == "Panel":
                asset["frame_style"] = str(raw.get("frame_style", "default")).strip() or "default"
        else:
            raise ValueError("each asset must be a semantic-name string or object")
        if not asset["semantic_name"]:
            raise ValueError("asset semantic_name cannot be empty")
        if category == "Panel":
            asset.setdefault("frame_style", "default")
            frame_key = str(asset["frame_style"]).casefold()
            existing = panel_by_frame_style.get(frame_key)
            if existing is not None:
                panel_aliases.append(
                    {
                        "semantic_name": asset["semantic_name"],
                        "state": asset["state"],
                        "frame_style": str(asset["frame_style"]),
                        "reuse_semantic_name": str(existing["semantic_name"]),
                        "reuse_state": str(existing["state"]),
                    }
                )
                continue
            panel_by_frame_style[frame_key] = asset
        asset["category_index"] = len(assets) + 1
        assets.append(asset)
    return assets, panel_aliases


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


def declared_subject_colors(
    category_spec: dict[str, Any],
    assets: list[dict[str, Any]],
    style_notes: str,
) -> set[str]:
    """Resolve deterministic color conflicts declared by Codex in the request."""
    conflicts: set[str] = set()
    for color in ("green", "magenta", "cyan"):
        if bool(category_spec.get(f"subject_uses_{color}", False)):
            conflicts.add(color)
    raw_colors = category_spec.get("subject_colors", [])
    if isinstance(raw_colors, str):
        raw_colors = [raw_colors]
    if not isinstance(raw_colors, list):
        raise ValueError("subject_colors must be a string or list")
    text = " ".join(
        [
            style_notes,
            *(str(value) for value in raw_colors),
            *(str(asset.get("description", "")) for asset in assets),
        ]
    ).casefold()
    for color, terms in COLOR_TERMS.items():
        if any(term.casefold() in text for term in terms):
            conflicts.add(color)
    return conflicts


def select_chroma_key(
    category_spec: dict[str, Any],
    assets: list[dict[str, Any]],
    style_notes: str,
) -> tuple[str, dict[str, Any]]:
    requested = str(category_spec.get("chroma_key", "auto")).upper()
    conflicts = declared_subject_colors(category_spec, assets, style_notes)
    if requested != "AUTO":
        selected = normalize_chroma_key(requested, bool(category_spec.get("subject_uses_green", False)))
        selected_color = next((name for value, name in CHROMA_CANDIDATES if value == selected), None)
        if selected_color in conflicts:
            raise ValueError(
                f"explicit chroma key {selected} conflicts with declared {selected_color} subject colors"
            )
        return selected, {
            "mode": "explicit",
            "selected": selected,
            "declared_conflicts": sorted(conflicts),
        }
    for value, color in CHROMA_CANDIDATES:
        if color not in conflicts:
            return value, {
                "mode": "auto-declared-palette",
                "selected": value,
                "declared_conflicts": sorted(conflicts),
            }
    raise ValueError(
        "all supported chroma keys conflict with declared subject colors; split the category or provide existing Alpha"
    )


def default_generation_budget(categories: list[dict[str, Any]]) -> dict[str, Any]:
    names = {str(category.get("category", "")) for category in categories}
    reserves: dict[str, int] = {}
    for category in ("Panel", "Button"):
        if category in names:
            reserves[category] = 1
    if names & {"Icon_Nav", "Icon_Status", "Icon_Item"}:
        reserves["chroma-risk-icons"] = 1
    global_fallback_calls = 1
    suggested = min(5, sum(reserves.values()) + global_fallback_calls)
    return {
        "max_extra_calls": suggested,
        "reserved_extra_calls": reserves,
        "global_fallback_calls": global_fallback_calls,
        "strategy": "risk-reserved",
    }


def normalize_unity_delivery(spec: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    raw = spec.get("unity_delivery")
    if raw is None:
        return {"enabled": False}
    if not isinstance(raw, dict):
        raise ValueError("unity_delivery must be an object")
    enabled = bool(raw.get("enabled", False))
    if not enabled:
        return {"enabled": False}
    if raw.get("layout_confirmed") is not True:
        raise ValueError("unity_delivery.layout_confirmed must be true")
    unity_project = str(raw.get("unity_project", "")).strip()
    unity_editor = str(raw.get("unity_editor", "")).strip()
    if not unity_project or not unity_editor:
        raise ValueError("enabled unity_delivery requires unity_project and unity_editor")
    if not Path(unity_project).is_absolute() or not Path(unity_editor).is_absolute():
        raise ValueError("unity_project and unity_editor must be absolute paths")

    layout_value = raw.get("layout")
    if isinstance(layout_value, dict):
        layout_payload = layout_value
    elif isinstance(layout_value, str) and layout_value.strip():
        layout_source = Path(layout_value).expanduser().resolve()
        if not layout_source.is_file():
            raise FileNotFoundError(f"Unity layout not found: {layout_source}")
        layout_payload = read_json(layout_source)
    else:
        raise ValueError("enabled unity_delivery requires layout as an object or JSON file path")
    if layout_payload.get("schema_version") != 1:
        raise ValueError("unity_delivery layout schema_version must be 1")
    normalize_layout(layout_payload)
    screens = layout_payload.get("screens")
    if not isinstance(screens, list) or not screens:
        raise ValueError("unity_delivery layout requires at least one screen")
    screen_ids: set[str] = set()
    for index, screen in enumerate(screens):
        if not isinstance(screen, dict):
            raise ValueError(f"unity_delivery.layout.screens[{index}] must be an object")
        screen_id = str(screen.get("id", "")).strip()
        if not screen_id or screen_id in screen_ids:
            raise ValueError(f"invalid duplicate Unity screen id at index {index}")
        screen_ids.add(screen_id)

    layout_path = run_dir / "unity" / "unity-layout.json"
    write_json(layout_path, layout_payload)
    return {
        "enabled": True,
        "layout_confirmed": True,
        "unity_project": unity_project,
        "unity_editor": unity_editor,
        "layout": "unity/unity-layout.json",
        "screen_count": len(screens),
        "screen_ids": sorted(screen_ids),
    }


def normalize_generation_policy(spec: dict[str, Any]) -> dict[str, Any]:
    raw = spec.get("generation_policy", {})
    if not isinstance(raw, dict):
        raise ValueError("generation_policy must be an object")
    mode = str(raw.get("mode", "adaptive-parallel"))
    if mode not in {"adaptive-parallel", "sequential-inputs"}:
        raise ValueError("generation_policy.mode must be adaptive-parallel or sequential-inputs")
    default_limit = 3 if mode == "adaptive-parallel" else 1
    max_concurrent = int(raw.get("max_concurrent_image_jobs", default_limit))
    if max_concurrent < 1 or max_concurrent > 3:
        raise ValueError("generation_policy.max_concurrent_image_jobs must be between 1 and 3")
    if mode == "sequential-inputs" and max_concurrent != 1:
        raise ValueError("sequential-inputs requires max_concurrent_image_jobs=1")
    return {
        "mode": mode,
        "max_concurrent_image_jobs": max_concurrent,
        "minimum_concurrent_image_jobs": 1,
        "max_concurrent_high_risk_jobs": min(2, max_concurrent),
        "high_risk_categories": ["Panel", "Button", "Icon_Status"],
        "dependent_inputs_serial": True,
        "retry_inputs_serial": True,
        "fallback_on": ["rate-limit", "timeout", "disconnect"],
        "rerun_orchestrator_after_each_wave": True,
    }


def prepare_batch(spec: dict[str, Any], run_dir: Path, force: bool = False) -> Path:
    project_id = slugify(str(spec.get("project_id", "game-ui")))
    categories = spec.get("categories")
    if not isinstance(categories, list) or not categories:
        raise ValueError("request requires a non-empty categories list")
    retry_policy = dict(spec.get("retry_policy", {}))
    max_attempts = int(retry_policy.get("max_attempts", 3))
    if max_attempts < 1 or max_attempts > 5:
        raise ValueError("retry_policy.max_attempts must be between 1 and 5")
    retry_policy = {"max_attempts": max_attempts, "single_cause_per_attempt": True}
    raw_budget = spec.get("generation_budget", {})
    if not isinstance(raw_budget, dict):
        raise ValueError("generation_budget must be an object")
    budget_defaults = default_generation_budget(categories)
    max_extra_calls = int(raw_budget.get("max_extra_calls", budget_defaults["max_extra_calls"]))
    minutes_per_call = raw_budget.get("estimated_minutes_per_call", [5, 8])
    if max_extra_calls < 0 or max_extra_calls > 5:
        raise ValueError("generation_budget.max_extra_calls must be between 0 and 5")
    if (
        not isinstance(minutes_per_call, list)
        or len(minutes_per_call) != 2
        or not all(isinstance(item, (int, float)) and item > 0 for item in minutes_per_call)
        or minutes_per_call[0] > minutes_per_call[1]
    ):
        raise ValueError("generation_budget.estimated_minutes_per_call must be [positive min, positive max]")
    generation_budget = {
        "max_extra_calls": max_extra_calls,
        "estimated_minutes_per_call": [float(minutes_per_call[0]), float(minutes_per_call[1])],
        "reserved_extra_calls": dict(budget_defaults["reserved_extra_calls"]),
        "global_fallback_calls": int(budget_defaults["global_fallback_calls"]),
        "strategy": "explicit-total" if "max_extra_calls" in raw_budget else str(budget_defaults["strategy"]),
    }
    style_consistency = dict(spec.get("style_consistency", {}))
    style_consistency = {
        "enabled": bool(style_consistency.get("enabled", True)),
        "warning_below": float(style_consistency.get("warning_below", 60)),
        "fail_below": float(style_consistency.get("fail_below", 40)),
    }
    if not 0 <= style_consistency["fail_below"] <= style_consistency["warning_below"] <= 100:
        raise ValueError("style_consistency thresholds must satisfy 0 <= fail_below <= warning_below <= 100")
    run_dir = run_dir.expanduser().resolve()
    if run_dir.exists() and any(run_dir.iterdir()) and not force:
        raise FileExistsError(f"output directory is not empty: {run_dir}; use --force to reuse it")

    for relative in (
        "references/layout-guides",
        "requests",
        "prompts",
        "generated/current",
        "extracted",
        "normalized",
        "final",
        "reused-staging",
        "qa",
        "unity",
        ".local/backups",
    ):
        (run_dir / relative).mkdir(parents=True, exist_ok=True)

    generation_policy = normalize_generation_policy(spec)

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
        assets, panel_aliases = category_assets(category_spec, category)
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
        if transparency_mode in {"native-alpha-required", "model-matte-derived"}:
            chroma_key = None
            chroma_key_selection = {"mode": "not-applicable", "selected": None, "declared_conflicts": []}
        else:
            chroma_key, chroma_key_selection = select_chroma_key(
                category_spec,
                assets,
                str(spec.get("style_notes", "")),
            )
        category_request = {
            "category": category,
            "canvas": canvas,
            "grid": grid,
            "target_size": target_size,
            "alignment": str(category_spec.get("alignment", defaults["alignment"])),
            "padding": int(category_spec.get("padding", 8)),
            "chroma_key": chroma_key,
            "chroma_key_selection": chroma_key_selection,
            "transparency_mode": transparency_mode,
            "generation_method": generation_method,
            "allow_attached_glow": bool(category_spec.get("allow_attached_glow", False)),
            "fragment_policy": category_spec.get("fragment_policy"),
            "assets": assets,
        }
        if panel_aliases:
            category_request["reuse_aliases"] = panel_aliases
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
                    "generation_sequence": len(jobs) + 1,
                    "risk_priority": RISK_PRIORITY.get(category, 10),
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
                    "generated_output": f"generated/current/{job_id}.png",
                    "alpha_matte_output": f"generated/current/{job_id}-alpha-matte.png"
                    if transparency_mode == "model-matte-derived" else None,
                    "transparency_mode": transparency_mode,
                    "provenance_file": f"generated/current/{job_id}.provenance.json"
                    if transparency_mode == "native-alpha-required" else None,
                    "final_directory": f"final/{category}",
                }
            )

    created_at = datetime.now(timezone.utc).isoformat()
    unity_delivery = normalize_unity_delivery(spec, run_dir)
    write_json(
        run_dir / "request.json",
        {
            "schema_version": 2,
            "project_id": project_id,
            "created_at": created_at,
            "style_notes": str(spec.get("style_notes", "")),
            "generation_method": generation_method,
            "generation_policy": generation_policy,
            "generation_budget": generation_budget,
            "retry_policy": retry_policy,
            "style_consistency": style_consistency,
            "references": references,
            "categories": normalized_categories,
            "expected_count": sum(len(item["assets"]) for item in normalized_categories),
            "unity_delivery": unity_delivery,
        },
    )
    write_json(
        run_dir / "jobs.json",
        {
            "schema_version": 2,
            "created_at": created_at,
            "generation_policy": generation_policy,
            "jobs": jobs,
        },
    )
    write_json(
        run_dir / "qa" / "request-preflight.json",
        {
            "schema_version": 1,
            "ok": True,
            "project_id": project_id,
            "job_count": len(jobs),
            "expected_count": sum(len(item["assets"]) for item in normalized_categories),
            "generation_policy": generation_policy,
            "generation_budget": generation_budget,
            "categories": [
                {
                    "category": item["category"],
                    "asset_count": len(item["assets"]),
                    "canvas": item["canvas"],
                    "grid": item["grid"],
                    "transparency_mode": item["transparency_mode"],
                    "chroma_key_selection": item["chroma_key_selection"],
                }
                for item in normalized_categories
            ],
            "unity_delivery": unity_delivery,
            "directory_contract": {
                "active_generation": "generated/current",
                "backups": ".local/backups",
                "reused_assets": "reused-staging",
                "formal_outputs": "final",
            },
            "checked_at": created_at,
        },
    )
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
