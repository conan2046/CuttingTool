#!/usr/bin/env python3
"""Compile approved UI reference analysis into notes, inventory, and a batch request."""

from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any


AUTO_BEGIN = "<!-- GAME-UI-ASSET-PIPELINE:AUTO-BEGIN -->"
AUTO_END = "<!-- GAME-UI-ASSET-PIPELINE:AUTO-END -->"
SUPPORTED_CATEGORIES = {
    "Panel",
    "Button",
    "Icon_Nav",
    "Icon_Status",
    "Icon_General",
    "Icon_Item",
    "Icon_Equip",
    "Icon_Skill",
    "Icon_Effect",
}
ITEM_ICON_POLICIES = {"generate", "empty-slots", "runtime-data"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def asset_key(category: str, semantic_name: str, state: str) -> str:
    return "|".join((category.strip(), semantic_name.strip().casefold(), state.strip().casefold()))


def load_catalog(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    payload = read_json(path)
    return {
        asset_key(str(item["category"]), str(item["semantic_name"]), str(item.get("state", "Default"))): item
        for item in payload.get("assets", [])
    }


def require_pair(value: Any, label: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 2 or not all(isinstance(item, int) and item > 0 for item in value):
        raise ValueError(f"{label} must be [positive width, positive height]")
    return list(value)


def validate_analysis(analysis: dict[str, Any]) -> None:
    if not str(analysis.get("project_id", "")).strip():
        raise ValueError("analysis requires project_id")
    canonical = analysis.get("canonical_reference")
    if not isinstance(canonical, dict) or not str(canonical.get("file", "")).strip():
        raise ValueError("analysis requires canonical_reference.file")
    screens = analysis.get("screens")
    if not isinstance(screens, list) or not screens:
        raise ValueError("analysis requires at least one screen")
    for screen_index, screen in enumerate(screens):
        if not isinstance(screen, dict):
            raise ValueError(f"screens[{screen_index}] must be an object")
        require_pair(screen.get("target_size"), f"screens[{screen_index}].target_size")
        if screen.get("layout_confirmed") is not True:
            raise ValueError(f"screens[{screen_index}].layout_confirmed must be true")
        if screen.get("elements_match_canonical") not in {True, False}:
            raise ValueError(f"screens[{screen_index}].elements_match_canonical must be true or false")
        if screen.get("elements_match_canonical") is False and not str(screen.get("difference_notes", "")).strip():
            raise ValueError(f"screens[{screen_index}].difference_notes is required when elements do not match")
        content_policy = screen.get("content_policy", {})
        if not isinstance(content_policy, dict):
            raise ValueError(f"screens[{screen_index}].content_policy must be an object")
        item_icons = str(content_policy.get("item_icons", "generate"))
        if item_icons not in ITEM_ICON_POLICIES:
            raise ValueError(
                f"screens[{screen_index}].content_policy.item_icons must be one of {sorted(ITEM_ICON_POLICIES)}"
            )
        assets = screen.get("assets")
        if not isinstance(assets, list) or not assets:
            raise ValueError(f"screens[{screen_index}].assets requires at least one asset")
        for asset_index, asset in enumerate(assets):
            if not isinstance(asset, dict):
                raise ValueError(f"screens[{screen_index}].assets[{asset_index}] must be an object")
            category = str(asset.get("category", ""))
            if category not in SUPPORTED_CATEGORIES:
                raise ValueError(f"unsupported category at screens[{screen_index}].assets[{asset_index}]: {category}")
            if not str(asset.get("semantic_name", "")).strip():
                raise ValueError(f"screens[{screen_index}].assets[{asset_index}].semantic_name is required")
    unity_delivery = analysis.get("unity_delivery")
    if unity_delivery is not None:
        if not isinstance(unity_delivery, dict):
            raise ValueError("unity_delivery must be an object")
        if bool(unity_delivery.get("enabled", False)):
            if unity_delivery.get("layout_confirmed") is not True:
                raise ValueError("unity_delivery.layout_confirmed must be true")
            if not str(unity_delivery.get("unity_project", "")).strip():
                raise ValueError("enabled unity_delivery requires unity_project")
            if not str(unity_delivery.get("unity_editor", "")).strip():
                raise ValueError("enabled unity_delivery requires unity_editor")
            for screen_index, screen in enumerate(screens):
                elements = screen.get("unity_elements")
                if not isinstance(elements, list) or not elements:
                    raise ValueError(
                        f"screens[{screen_index}].unity_elements requires an explicit non-empty layout"
                    )


def managed_markdown(existing: str, generated: str) -> str:
    block = f"{AUTO_BEGIN}\n{generated.rstrip()}\n{AUTO_END}\n"
    if AUTO_BEGIN in existing and AUTO_END in existing:
        pattern = re.compile(re.escape(AUTO_BEGIN) + r".*?" + re.escape(AUTO_END) + r"\n?", re.DOTALL)
        return pattern.sub(lambda _: block, existing, count=1)
    if not existing.strip():
        return block
    return existing.rstrip() + "\n\n" + block


def render_reference_notes(analysis: dict[str, Any]) -> str:
    canonical = analysis["canonical_reference"]
    lines = [
        f"# {analysis.get('project_name', analysis['project_id'])} 参考图与制作确认",
        "",
        "> 本区由 Codex 根据参考图和用户确认自动维护；无需用户手工填写。",
        "",
        "## 主参考图",
        "",
        f"- 文件：`{canonical['file']}`",
        f"- 作用：{canonical.get('role', '锁定整体视觉风格与首界面布局')}",
        f"- 自动分析：{canonical.get('analysis', '已通过清晰度、完整性与风格代表性检查')}",
        "",
        "## 辅助参考图",
        "",
    ]
    supports = analysis.get("supporting_references", [])
    if supports:
        for item in supports:
            lines.append(
                f"- `{item['file']}`：只参考 {item.get('use', '补充视觉信息')}；不参考 {item.get('exclude', '未指定内容')}。"
            )
    else:
        lines.append("- 无。")
    lines.extend(["", "## 界面确认", ""])
    for index, screen in enumerate(analysis["screens"], start=1):
        width, height = screen["target_size"]
        match = "一致" if screen["elements_match_canonical"] else "不一致"
        details = screen.get("difference_notes", "无")
        lines.extend(
            [
                f"### {index}. {screen.get('name', screen.get('id', f'Screen{index}'))}",
                "",
                f"- 界面尺寸：`{width}×{height}`",
                f"- 布局参考：`{screen.get('layout_reference', canonical['file'])}`",
                "- 布局：用户已确认",
                f"- UI 元素与主参考：{match}",
                f"- 差异说明：{details}",
                "",
            ]
        )
    return "\n".join(lines)


def compile_inventory(analysis: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inventory: list[dict[str, Any]] = []
    generated_in_request: dict[str, dict[str, Any]] = {}
    generation_assets: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for screen_index, screen in enumerate(analysis["screens"]):
        item_icon_policy = str(screen.get("content_policy", {}).get("item_icons", "generate"))
        for asset in screen["assets"]:
            category = str(asset["category"])
            semantic_name = str(asset["semantic_name"]).strip()
            state = str(asset.get("state", "Default")).strip() or "Default"
            key = asset_key(category, semantic_name, state)
            excluded = category == "Icon_Item" and item_icon_policy in {"empty-slots", "runtime-data"}
            reuse = None if excluded or screen_index == 0 else generated_in_request.get(key) or catalog.get(key)
            action = "exclude" if excluded else ("reuse" if reuse else "generate")
            record = {
                "screen_id": str(screen.get("id", f"screen-{screen_index + 1:02d}")),
                "screen_name": str(screen.get("name", screen.get("id", f"Screen {screen_index + 1}"))),
                "screen_size": list(screen["target_size"]),
                "category": category,
                "semantic_name": semantic_name,
                "state": state,
                "description": str(asset.get("description", "")).strip(),
                "action": action,
                "content_policy": item_icon_policy if category == "Icon_Item" else None,
                "exclusion_reason": f"item-icons:{item_icon_policy}" if excluded else None,
                "reuse_asset_id": reuse.get("id") if reuse else None,
                "reuse_output": reuse.get("output") if reuse else None,
                "reuse_source_run": reuse.get("source_run") if reuse else None,
            }
            inventory.append(record)
            if action == "generate":
                generated_in_request[key] = {
                    "id": f"pending:{category}:{semantic_name}:{state}",
                    "output": "本次生成后写入 Manifest",
                    "source_run": "current-run",
                }
                if key not in generation_assets:
                    generation_assets[key] = {
                        "category": category,
                        "semantic_name": semantic_name,
                        "state": state,
                        "description": record["description"],
                    }
    return inventory, list(generation_assets.values())


def render_inventory(analysis: dict[str, Any], inventory: list[dict[str, Any]]) -> str:
    lines = [
        f"# {analysis.get('project_name', analysis['project_id'])} UI 资源清单",
        "",
        "> 首个界面全部生成；后续界面按 类别 + 语义名 + 状态 复用，目标尺寸不参与复用判定。",
        "",
        "| 界面 | 界面尺寸 | 类别 | 资源 | 状态 | 动作 | 引用资源 |",
        "|---|---:|---|---|---|---|---|",
    ]
    for item in inventory:
        width, height = item["screen_size"]
        reference = item["reuse_asset_id"] or "-"
        lines.append(
            f"| {item['screen_name']} | {width}×{height} | {item['category']} | {item['semantic_name']} | {item['state']} | {item['action']} | {reference} |"
        )
    return "\n".join(lines) + "\n"


def build_batch_request(analysis: dict[str, Any], generation_assets: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for asset in generation_assets:
        grouped.setdefault(asset["category"], []).append(
            {
                "semantic_name": asset["semantic_name"],
                "state": asset["state"],
                "description": asset["description"],
            }
        )
    unity_delivery = build_unity_delivery(analysis)
    generation_budget = {
        "max_extra_calls": int(analysis.get("generation_budget", {}).get("max_extra_calls", 1)),
        "estimated_minutes_per_call": list(
            analysis.get("generation_budget", {}).get("estimated_minutes_per_call", [5, 8])
        ),
    }
    if not grouped:
        return {
            "schema_version": 2,
            "project_id": analysis["project_id"],
            "generation_method": "built-in-imagegen",
            "categories": [],
            "all_assets_reused": True,
            "generation_policy": {
                "mode": "sequential-inputs",
                "max_concurrent_image_jobs": 1,
                "rerun_orchestrator_after_each_input": True,
            },
            "generation_budget": generation_budget,
            "unity_delivery": unity_delivery,
        }
    category_settings = analysis.get("category_settings", {})
    categories = []
    for category, assets in grouped.items():
        settings = dict(category_settings.get(category, {}))
        categories.append({"category": category, **settings, "assets": assets})
    return {
        "schema_version": 2,
        "project_id": analysis["project_id"],
        "style_notes": str(analysis.get("style_notes", "")),
        "generation_method": str(analysis.get("generation_method", "built-in-imagegen")),
        "generation_policy": {
            "mode": "sequential-inputs",
            "max_concurrent_image_jobs": 1,
            "rerun_orchestrator_after_each_input": True,
        },
        "generation_budget": generation_budget,
        "canonical_style": str(analysis["canonical_reference"]["file"]),
        "references": [str(item["file"]) for item in analysis.get("supporting_references", [])],
        "categories": categories,
        "unity_delivery": unity_delivery,
    }


def build_unity_delivery(analysis: dict[str, Any]) -> dict[str, Any]:
    raw = analysis.get("unity_delivery")
    if not isinstance(raw, dict) or not bool(raw.get("enabled", False)):
        return {"enabled": False}
    screens = []
    for index, screen in enumerate(analysis["screens"], start=1):
        screens.append(
            {
                "id": str(screen.get("id", f"screen-{index:02d}")),
                "name": str(screen.get("name", screen.get("id", f"Screen {index}"))),
                "reference_size": list(screen["target_size"]),
                "elements": list(screen["unity_elements"]),
            }
        )
    layout: dict[str, Any] = {"schema_version": 1, "screens": screens}
    for field in ("nine_slice_overrides", "pixels_per_unit_overrides"):
        if field in raw:
            layout[field] = raw[field]
    return {
        "enabled": True,
        "layout_confirmed": True,
        "unity_project": str(raw["unity_project"]),
        "unity_editor": str(raw["unity_editor"]),
        "layout": layout,
    }


def compile_intake(project_dir: Path, analysis: dict[str, Any]) -> dict[str, Any]:
    validate_analysis(analysis)
    project_dir = project_dir.expanduser().resolve()
    references_dir = project_dir / "references"
    references_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = project_dir / "ui-asset-catalog.json"
    inventory, generation_assets = compile_inventory(analysis, load_catalog(catalog_path))

    notes_path = references_dir / "reference-notes.md"
    existing_notes = notes_path.read_text(encoding="utf-8") if notes_path.is_file() else ""
    notes_path.write_text(managed_markdown(existing_notes, render_reference_notes(analysis)), encoding="utf-8")
    inventory_md = project_dir / "ui-resource-inventory.md"
    inventory_md.write_text(render_inventory(analysis, inventory), encoding="utf-8")
    inventory_json = project_dir / "ui-resource-inventory.json"
    write_json(inventory_json, {"schema_version": 1, "project_id": analysis["project_id"], "assets": inventory})
    request_path = project_dir / "batch-request.json"
    batch_request = build_batch_request(analysis, generation_assets)
    write_json(request_path, batch_request)
    return {
        "ok": True,
        "project_id": analysis["project_id"],
        "reference_notes": str(notes_path),
        "inventory_markdown": str(inventory_md),
        "inventory_json": str(inventory_json),
        "batch_request": str(request_path),
        "generate_count": len(generation_assets),
        "reuse_count": sum(1 for item in inventory if item["action"] == "reuse"),
        "all_assets_reused": not generation_assets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True, type=Path)
    parser.add_argument("--analysis", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = compile_intake(args.project_dir, read_json(args.analysis))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
