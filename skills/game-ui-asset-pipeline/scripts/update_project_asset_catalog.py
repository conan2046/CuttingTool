#!/usr/bin/env python3
"""Merge a completed run Manifest into the project-level reusable asset catalog."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def asset_key(item: dict[str, Any]) -> str:
    return "|".join(
        (
            str(item["category"]).strip(),
            str(item["semantic_name"]).strip().casefold(),
            str(item.get("state", "Default")).strip().casefold(),
        )
    )


def update_catalog(catalog_path: Path, manifest_path: Path, source_run: str) -> dict[str, Any]:
    catalog_path = catalog_path.expanduser().resolve()
    manifest_path = manifest_path.expanduser().resolve()
    manifest = read_json(manifest_path)
    existing = read_json(catalog_path) if catalog_path.is_file() else {"schema_version": 1, "assets": []}
    merged = {asset_key(item): item for item in existing.get("assets", [])}
    added = 0
    updated = 0
    for source in manifest.get("assets", []):
        if str(source.get("qa", "pass")) == "fail":
            continue
        key = asset_key(source)
        record = {
            "id": str(source["id"]),
            "category": str(source["category"]),
            "semantic_name": str(source["semantic_name"]),
            "state": str(source.get("state", "Default")),
            "output": str(source["output"]),
            "source_run": source_run,
            "width": int(source.get("width", 0)),
            "height": int(source.get("height", 0)),
            "qa": str(source.get("qa", "pass")),
        }
        if key in merged:
            updated += 1
        else:
            added += 1
        merged[key] = record
    payload = {
        "schema_version": 1,
        "project_id": str(manifest.get("project_id", existing.get("project_id", "game-ui"))),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "assets": [merged[key] for key in sorted(merged)],
    }
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "catalog": str(catalog_path), "added": added, "updated": updated, "total": len(merged)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-run", required=True)
    args = parser.parse_args()
    try:
        result = update_catalog(args.catalog, args.manifest, args.source_run)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
