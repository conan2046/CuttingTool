#!/usr/bin/env python3
"""Run the complete Unity export: prepare assets, configure sprites, and build prefabs."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from prepare_unity_export import prepare_unity_export, read_json


EXECUTE_METHOD = "CuttingTool.GameUI.Editor.GameUIBatchImporter.RunFromCommandLine"


def export_unity_ui(
    run_dir: Path,
    unity_project: Path,
    unity_editor: Path,
    layout: Path,
    package_source: Path,
    import_root: str = "Assets/_Generated/GameUI",
) -> dict[str, Any]:
    run_dir = run_dir.expanduser().resolve()
    unity_project = unity_project.expanduser().resolve()
    unity_editor = unity_editor.expanduser().resolve()
    if not unity_editor.is_file():
        raise FileNotFoundError(f"Unity Editor not found: {unity_editor}")
    preflight = prepare_unity_export(
        run_dir,
        unity_project,
        package_source,
        layout,
        import_root,
    )
    if not preflight["ok"]:
        return {"ok": False, "status": "preflight-failed", **preflight}

    unity_dir = run_dir / "unity"
    plan_path = unity_dir / "unity-import-plan.json"
    report_path = unity_dir / "unity-import-report.json"
    log_path = unity_dir / "unity-batch.log"
    report_path.unlink(missing_ok=True)
    log_path.unlink(missing_ok=True)
    command = [
        str(unity_editor),
        "-batchmode",
        "-quit",
        "-nographics",
        "-projectPath",
        str(unity_project),
        "-executeMethod",
        EXECUTE_METHOD,
        "-gameUIPlan",
        str(plan_path),
        "-logFile",
        str(log_path),
    ]
    completed = subprocess.run(command, check=False)
    if not report_path.is_file():
        return {
            "ok": False,
            "status": "unity-failed-without-report",
            "returncode": completed.returncode,
            "log": str(log_path),
        }
    report = read_json(report_path)
    return {
        "ok": completed.returncode == 0 and bool(report.get("ok")),
        "status": "complete" if completed.returncode == 0 and report.get("ok") else "unity-failed",
        "returncode": completed.returncode,
        "plan": str(plan_path),
        "report": str(report_path),
        "log": str(log_path),
        "results": report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--unity-project", required=True, type=Path)
    parser.add_argument("--unity-editor", required=True, type=Path)
    parser.add_argument("--layout", required=True, type=Path)
    parser.add_argument("--package-source", type=Path, default=Path(__file__).resolve().parents[1] / "assets" / "unity-package")
    parser.add_argument("--import-root", default="Assets/_Generated/GameUI")
    args = parser.parse_args()
    try:
        result = export_unity_ui(
            args.run_dir,
            args.unity_project,
            args.unity_editor,
            args.layout,
            args.package_source,
            args.import_root,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
