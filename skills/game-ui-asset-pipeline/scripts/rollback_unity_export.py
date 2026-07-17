#!/usr/bin/env python3
"""Safely remove one generated Unity UI export using its rollback manifest."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def resolve_project_child(project: Path, relative: str, allowed_root: str) -> Path:
    normalized = relative.replace("\\", "/").strip("/")
    if not normalized.startswith(allowed_root) or ".." in normalized.split("/"):
        raise ValueError(f"rollback path is outside {allowed_root}: {relative}")
    target = (project / normalized).resolve()
    try:
        target.relative_to(project)
    except ValueError as error:
        raise ValueError(f"rollback path escapes Unity project: {relative}") from error
    return target


def rollback(manifest_path: Path, remove_package: bool = False) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    project = Path(str(manifest["unity_project"])).expanduser().resolve()
    if not (project / "ProjectSettings" / "ProjectVersion.txt").is_file():
        raise ValueError(f"rollback Unity project is invalid: {project}")
    generated = resolve_project_child(project, str(manifest["generated_root"]), "Assets/_Generated/GameUI/")
    removed: list[str] = []
    if generated.is_dir():
        shutil.rmtree(generated)
        removed.append(str(generated))
    meta = Path(str(generated) + ".meta")
    if meta.is_file():
        meta.unlink()
        removed.append(str(meta))
    if remove_package:
        package = resolve_project_child(project, str(manifest["embedded_package"]), "Packages/com.hongda.game-ui-asset-pipeline")
        if package.is_dir():
            shutil.rmtree(package)
            removed.append(str(package))
        package_meta = Path(str(package) + ".meta")
        if package_meta.is_file():
            package_meta.unlink()
            removed.append(str(package_meta))
    return {"ok": True, "unity_project": str(project), "removed": removed}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--remove-package", action="store_true")
    args = parser.parse_args()
    try:
        result = rollback(args.manifest, args.remove_package)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
