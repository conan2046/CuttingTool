#!/usr/bin/env python3
"""Initialize a local game UI input project without overwriting user notes."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def slugify(value: str) -> str:
    project_id = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-_").lower()
    if not project_id:
        raise ValueError("project name must contain at least one English letter or digit")
    return project_id


def build_reference_notes(project_name: str, project_id: str) -> str:
    return f"""# {project_name} 参考图说明

> 项目标识：`{project_id}`
> 本文件由 game-ui-asset-pipeline 首次初始化创建。请填写参考图作用；再次初始化不会覆盖本文件。

## 主参考图

<!-- 填写说明：主参考图只能有一张。把图片放进本目录后，将“状态”改为“已放置”。 -->
> 填写示例：`canonical-style.png｜已放置｜锁定国风修仙、青玉鎏金材质、正面视角和柔和金色光照。`

| 文件名 | 状态 | 作用 |
|---|---|---|
| `canonical-style.png` | 待放置/待确认 | 最高优先级，锁定整体风格、材质、描边、配色、光照和观察角度 |

## 辅助参考图

<!-- 填写说明：每张辅助图只承担一个作用。没有某类辅助图时，可以删除对应行。 -->
> 填写示例：`reference-01-material.png｜只参考玉石和鎏金材质｜不参考界面布局和图标造型。`

| 顺序 | 文件名 | 只参考什么 | 不参考什么 |
|---:|---|---|---|
| 1 | `reference-01-material.png` | 待填写 | 待填写 |
| 2 | `reference-02-color.png` | 待填写 | 待填写 |
| 3 | `reference-03-shape.png` | 待填写 | 待填写 |

## 项目需求

<!-- 填写说明：不知道的项目可保留“自动判断”；资源名称尽量写清数量。 -->
> 填写示例：`国风修仙放置手游；手机端背包界面；4个道具图标；目标尺寸128×128。`

- 游戏类型与使用场景：待填写
- 目标平台：待填写
- 资源类别：待填写
- 资源清单与数量：待填写
- 目标尺寸：自动判断
- 透明模式：自动判断
- 禁止项：文字、数字、Logo、水印、棋盘格、可见网格

## 使用提醒

- 只保留一张最高优先级主参考图。
- 辅助图必须说明单一作用；风格冲突时拆成不同项目。
- 图片建议使用 PNG、JPG 或 WebP，英文文件名且不含空格。
- 放图完成后回到 Codex 回复“已放好”，不要自行启动后续脚本。
"""


def initialize_project(workspace_root: Path, project_name: str) -> dict[str, object]:
    display_name = project_name.strip()
    if not display_name:
        raise ValueError("project name cannot be empty")
    project_id = slugify(display_name)
    workspace_root = workspace_root.expanduser().resolve()
    project_dir = workspace_root / "input" / project_id
    references_dir = project_dir / "references"
    references_dir.mkdir(parents=True, exist_ok=True)
    notes_path = references_dir / "reference-notes.md"
    created = not notes_path.exists()
    if created:
        notes_path.write_text(build_reference_notes(display_name, project_id), encoding="utf-8")
    return {
        "ok": True,
        "project_name": display_name,
        "project_id": project_id,
        "created": created,
        "project_dir": str(project_dir),
        "references_dir": str(references_dir),
        "reference_notes": str(notes_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--project-name", required=True)
    args = parser.parse_args()
    try:
        result = initialize_project(args.workspace_root, args.project_name)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
