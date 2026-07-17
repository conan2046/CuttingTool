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
> 本文件由 game-ui-asset-pipeline 初始化。放入参考图后，Codex 会自动分析并更新自动维护区；用户无需手工填写。

<!-- GAME-UI-ASSET-PIPELINE:AUTO-BEGIN -->
## 等待自动分析

- 主参考图：等待 Codex 识别。
- 辅助参考图：等待 Codex 识别职责与排除项。
- 界面布局、UI 元素一致性和目标尺寸：等待用户一次性确认。
<!-- GAME-UI-ASSET-PIPELINE:AUTO-END -->

## 使用提醒

- 推荐只保留一张 `canonical-style.png` 作为最高优先级主参考图。
- 辅助图按 `reference-01-material.png` 等英文名称放置；职责由 Codex 自动判断并写入。
- 图片建议使用 PNG、JPG 或 WebP，英文文件名且不含空格。
- 放图完成后回到 Codex 回复“已放好”；之后只需确认界面布局、元素一致性与尺寸。
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
