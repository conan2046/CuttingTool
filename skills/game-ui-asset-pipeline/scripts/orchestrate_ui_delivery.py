#!/usr/bin/env python3
"""Prepare, resume, run, and summarize a complete Codex-first UI asset delivery."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from prepare_ui_batch import prepare_batch
from run_ui_pipeline import run_pipeline


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def required_inputs(job: dict[str, Any], run_dir: Path) -> list[dict[str, Any]]:
    requirements = [
        {
            "kind": "production-sheet",
            "path": str(job["generated_output"]),
            "prompt_file": str(job["prompt_file"]),
            "input_images": list(job.get("input_images", [])),
        }
    ]
    mode = str(job.get("transparency_mode", "chroma-key"))
    if mode == "model-matte-derived":
        requirements.append(
            {
                "kind": "alpha-matte",
                "path": str(job["alpha_matte_output"]),
                "prompt_file": str(job["alpha_matte_prompt_file"]),
                "edit_source": str(job["generated_output"]),
            }
        )
    if mode == "native-alpha-required":
        requirements.append(
            {
                "kind": "native-alpha-provenance",
                "path": str(job["provenance_file"]),
                "source": str(job["generated_output"]),
            }
        )
    for requirement in requirements:
        requirement["exists"] = (run_dir / str(requirement["path"])).is_file()
    return requirements


def generation_state(jobs: list[dict[str, Any]], run_dir: Path) -> dict[str, Any]:
    job_states: list[dict[str, Any]] = []
    required_count = 0
    ready_input_count = 0
    for job in jobs:
        inputs = required_inputs(job, run_dir)
        missing = [str(item["path"]) for item in inputs if not item["exists"]]
        required_count += len(inputs)
        ready_input_count += len(inputs) - len(missing)
        job_states.append(
            {
                "id": str(job["id"]),
                "category": str(job["category"]),
                "transparency_mode": str(job.get("transparency_mode", "chroma-key")),
                "expected_count": int(job["expected_count"]),
                "ready": not missing,
                "required_inputs": inputs,
                "missing_inputs": missing,
            }
        )
    ready_jobs = sum(1 for job in job_states if job["ready"])
    return {
        "job_count": len(job_states),
        "ready_job_count": ready_jobs,
        "pending_job_count": len(job_states) - ready_jobs,
        "required_input_count": required_count,
        "ready_input_count": ready_input_count,
        "missing_input_count": required_count - ready_input_count,
        "jobs": job_states,
    }


def existing_run_summary(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "qa" / "run-summary.json"
    return read_json(path) if path.is_file() else None


def delivery_results(run_summary: dict[str, Any] | None, expected: int) -> dict[str, Any]:
    if not run_summary:
        return {
            "expected": expected,
            "exported": 0,
            "pass": 0,
            "warning": 0,
            "fail": 0,
            "manual_action_required": [],
        }
    results = dict(run_summary.get("results", {}))
    return {
        "expected": int(results.get("expected", expected)),
        "exported": int(results.get("exported", 0)),
        "pass": int(results.get("pass", 0)),
        "warning": int(results.get("warning", 0)),
        "fail": int(results.get("fail", 0)),
        "manual_action_required": list(results.get("manual_action_required", [])),
    }


def build_summary(
    run_dir: Path,
    request: dict[str, Any],
    generation: dict[str, Any],
    status: str,
    run_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generation = {"method": str(request.get("generation_method", "built-in-imagegen")), **generation}
    results = delivery_results(run_summary, int(request.get("expected_count", 0)))
    missing = [
        path
        for job in generation["jobs"]
        for path in job["missing_inputs"]
    ]
    if status == "awaiting-generation":
        next_actions = [
            "按各 Job 的 Prompt 与参考图角色生成全部缺失输入。",
            "按精确相对路径保存结果，然后再次运行编排器。",
        ]
    elif status == "complete":
        next_actions = ["交付资源包前人工检查 qa/contact-sheet.png。"]
    else:
        next_actions = [
            "检查 qa/qa-report.json 和 Job 级报告。",
            "修正或重新生成问题 Job；若已存在正式 Manifest，使用 --force-run 重跑。",
        ]
    return {
        "schema_version": 1,
        "project_id": str(request.get("project_id", "game-ui")),
        "status": status,
        "complete": status == "complete",
        "run_dir": ".",
        "generation": generation,
        "missing_inputs": missing,
        "results": results,
        "outputs": {
            "final_directory": "final",
            "manifest": "final/manifest.json" if (run_dir / "final" / "manifest.json").is_file() else None,
            "contact_sheet": "qa/contact-sheet.png" if (run_dir / "qa" / "contact-sheet.png").is_file() else None,
            "qa_report": "qa/qa-report.json" if (run_dir / "qa" / "qa-report.json").is_file() else None,
            "run_summary": "qa/run-summary.json" if (run_dir / "qa" / "run-summary.json").is_file() else None,
            "delivery_summary": "qa/delivery-summary.json",
            "delivery_markdown": "qa/delivery-summary.md",
        },
        "next_actions": next_actions,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def render_markdown(summary: dict[str, Any]) -> str:
    generation = summary["generation"]
    results = summary["results"]
    lines = [
        f"# {summary['project_id']} 交付摘要",
        "",
        f"- 状态：`{summary['status']}`",
        f"- Job：{generation['ready_job_count']}/{generation['job_count']} 就绪",
        f"- 必需生成输入：{generation['ready_input_count']}/{generation['required_input_count']} 就绪",
        f"- 资源：{results['exported']}/{results['expected']} 已导出",
        f"- 结果：{results['pass']} pass / {results['warning']} warning / {results['fail']} fail",
    ]
    if summary["missing_inputs"]:
        lines.extend(["", "## 待生成文件", ""])
        lines.extend(f"- `{path}`" for path in summary["missing_inputs"])
    lines.extend(["", "## 交付文件", ""])
    for label, value in summary["outputs"].items():
        if value:
            lines.append(f"- {label}: `{value}`")
    lines.extend(["", "## 下一步", ""])
    lines.extend(f"- {action}" for action in summary["next_actions"])
    return "\n".join(lines) + "\n"


def write_delivery_summary(run_dir: Path, summary: dict[str, Any]) -> None:
    write_json(run_dir / "qa" / "delivery-summary.json", summary)
    markdown_path = run_dir / "qa" / "delivery-summary.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")


def orchestrate(
    run_dir: Path,
    request_path: Path | None = None,
    force_run: bool = False,
    transparent_threshold: float = 12.0,
    opaque_threshold: float = 96.0,
    adaptive_chroma: bool = True,
) -> dict[str, Any]:
    run_dir = run_dir.expanduser().resolve()
    request_file = run_dir / "request.json"
    jobs_file = run_dir / "jobs.json"
    prepared = request_file.is_file() and jobs_file.is_file()
    if request_file.is_file() != jobs_file.is_file():
        raise RuntimeError("run directory is incomplete: request.json and jobs.json must both exist")
    if not prepared:
        if request_path is None:
            raise FileNotFoundError("unprepared run requires --request")
        prepare_batch(read_json(request_path), run_dir)

    request = read_json(request_file)
    jobs_payload = read_json(jobs_file)
    jobs = list(jobs_payload.get("jobs", []))
    if not jobs:
        raise ValueError("jobs.json contains no jobs")
    generation = generation_state(jobs, run_dir)
    for job, state in zip(jobs, generation["jobs"]):
        if str(job.get("status", "")) not in {"processed", "failed"}:
            job["status"] = "ready-for-processing" if state["ready"] else "awaiting-generation"
    jobs_payload["jobs"] = jobs
    jobs_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(jobs_file, jobs_payload)

    if generation["missing_input_count"]:
        summary = build_summary(run_dir, request, generation, "awaiting-generation", existing_run_summary(run_dir))
        write_delivery_summary(run_dir, summary)
        return {"ok": True, **summary}

    prior_summary = existing_run_summary(run_dir)
    final_manifest = run_dir / "final" / "manifest.json"
    if prior_summary and prior_summary.get("status") == "complete" and final_manifest.is_file() and not force_run:
        summary = build_summary(run_dir, request, generation, "complete", prior_summary)
        write_delivery_summary(run_dir, summary)
        return {"ok": True, "reused_existing_delivery": True, **summary}

    if final_manifest.is_file() and not force_run:
        summary = build_summary(run_dir, request, generation, "failed", prior_summary)
        summary["next_actions"].append("正式 Manifest 已存在；修正后必须使用 --force-run 重跑。")
        write_delivery_summary(run_dir, summary)
        return {"ok": False, **summary}

    result = run_pipeline(
        run_dir,
        transparent_threshold=transparent_threshold,
        opaque_threshold=opaque_threshold,
        adaptive_chroma=adaptive_chroma,
        force=force_run,
    )
    run_summary = existing_run_summary(run_dir)
    status = "complete" if result["ok"] else "failed"
    summary = build_summary(run_dir, request, generation, status, run_summary)
    write_delivery_summary(run_dir, summary)
    return {"ok": result["ok"], **summary}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--request", type=Path, help="Batch request JSON; required only for a new run")
    parser.add_argument("--force-run", action="store_true", help="Rerun deterministic processing")
    parser.add_argument("--transparent-threshold", type=float, default=12.0)
    parser.add_argument("--opaque-threshold", type=float, default=96.0)
    parser.add_argument("--fixed-chroma-thresholds", action="store_true")
    args = parser.parse_args()
    if args.opaque_threshold <= args.transparent_threshold:
        parser.error("opaque-threshold must be greater than transparent-threshold")
    result = orchestrate(
        args.run_dir,
        request_path=args.request,
        force_run=args.force_run,
        transparent_threshold=args.transparent_threshold,
        opaque_threshold=args.opaque_threshold,
        adaptive_chroma=not args.fixed_chroma_thresholds,
    )
    print(json.dumps(result, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
