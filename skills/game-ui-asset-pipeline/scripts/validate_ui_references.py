#!/usr/bin/env python3
"""Validate local UI reference files before any generation work begins."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError


ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
IGNORED_FILENAMES = {"reference-notes.md", "thumbs.db", ".ds_store"}
CANONICAL_PATTERN = re.compile(r"canonical-style\.(?:png|jpe?g|webp)", re.IGNORECASE)
SUPPORTING_PATTERN = re.compile(r"reference-(\d{2})-[a-z0-9][a-z0-9_-]*\.(?:png|jpe?g|webp)", re.IGNORECASE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def issue(code: str, file: str | None, message: str, suggestion: str) -> dict[str, str | None]:
    return {"code": code, "severity": "fail", "file": file, "message": message, "suggestion": suggestion}


def validate_references(references_dir: Path) -> dict[str, Any]:
    references_dir = references_dir.expanduser().resolve()
    issues: list[dict[str, str | None]] = []
    images: list[dict[str, Any]] = []
    if not references_dir.is_dir():
        issues.append(issue("missing-references-directory", None, "参考图目录不存在。", "先运行项目初始化脚本。"))
        return build_result(references_dir, images, issues)

    notes = references_dir / "reference-notes.md"
    if not notes.is_file():
        issues.append(issue("missing-reference-notes", "reference-notes.md", "参考图说明文件不存在。", "重新运行项目初始化脚本恢复说明文件。"))

    candidates = [path for path in sorted(references_dir.iterdir(), key=lambda item: item.name.lower()) if path.is_file()]
    canonical_count = 0
    seen_hashes: dict[str, str] = {}
    supporting_indices: list[int] = []
    for path in candidates:
        lower_name = path.name.lower()
        if lower_name in IGNORED_FILENAMES:
            continue
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            issues.append(issue("unsupported-reference-file", path.name, "文件不是受支持的静态图片。", "请替换为 PNG、JPG、JPEG 或 WebP。"))
            continue

        if CANONICAL_PATTERN.fullmatch(path.name):
            role = "canonical-ui-style"
            canonical_count += 1
        else:
            match = SUPPORTING_PATTERN.fullmatch(path.name)
            if match is None:
                issues.append(issue("invalid-reference-name", path.name, "文件名不符合参考图命名规则。", "主图使用 canonical-style，辅助图使用 reference-01-material 等英文名。"))
                continue
            role = "supporting-style-reference"
            supporting_indices.append(int(match.group(1)))

        try:
            with Image.open(path) as source:
                frame_count = int(getattr(source, "n_frames", 1))
                image_format = str(source.format or "unknown")
                width, height = source.size
                source.verify()
        except (OSError, UnidentifiedImageError) as error:
            issues.append(issue("unreadable-reference-image", path.name, f"图片无法读取：{error}", "请重新导出或替换图片。"))
            continue

        if frame_count != 1:
            issues.append(issue("animated-reference-image", path.name, "参考图包含多个动画帧。", "请导出为单帧静态 PNG、JPG 或 WebP。"))
        if width < 256 or height < 256:
            issues.append(issue("reference-too-small", path.name, f"图片尺寸为 {width}×{height}，低于 256×256。", "请替换为宽高均不少于 256 像素的清晰图片。"))

        digest = sha256(path)
        duplicate = seen_hashes.get(digest)
        if duplicate is not None:
            issues.append(issue("duplicate-reference-content", path.name, f"图片内容与 {duplicate} 完全相同。", "请删除重复图片或换成承担不同职责的参考图。"))
        else:
            seen_hashes[digest] = path.name
        images.append(
            {
                "file": path.name,
                "path": str(path),
                "role": role,
                "format": image_format,
                "width": width,
                "height": height,
                "frames": frame_count,
                "sha256": digest,
            }
        )

    if not images:
        issues.append(issue("no-reference-images", None, "目录中没有有效参考图。", "至少放入一张符合命名规则的 PNG、JPG、JPEG 或 WebP。"))
    if canonical_count > 1:
        issues.append(issue("multiple-canonical-references", None, "检测到多张主参考图。", "只保留一张 canonical-style 图片，其余改为辅助参考图。"))
    if len(supporting_indices) != len(set(supporting_indices)):
        issues.append(issue("duplicate-supporting-index", None, "辅助参考图序号重复。", "按 reference-01、reference-02 连续使用唯一序号。"))
    return build_result(references_dir, images, issues)


def build_result(references_dir: Path, images: list[dict[str, Any]], issues: list[dict[str, str | None]]) -> dict[str, Any]:
    canonical_count = sum(1 for image in images if image["role"] == "canonical-ui-style")
    return {
        "schema_version": 1,
        "ok": not issues,
        "status": "ready-for-visual-review" if not issues else "awaiting-user-references",
        "references_dir": str(references_dir),
        "image_count": len(images),
        "canonical_count": canonical_count,
        "supporting_count": len(images) - canonical_count,
        "requires_canonical_generation": not issues and canonical_count == 0,
        "images": images,
        "issues": issues,
        "next_action": "使用 view_image 逐张视觉检查。" if not issues else "请用户按 issues 替换参考图后重新完整检查。",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--references-dir", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = validate_references(args.references_dir)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["ok"] else 2)


if __name__ == "__main__":
    main()
