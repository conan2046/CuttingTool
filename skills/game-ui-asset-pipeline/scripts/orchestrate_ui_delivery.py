#!/usr/bin/env python3
"""Prepare, resume, run, and summarize a complete Codex-first UI asset delivery."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from prepare_ui_batch import prepare_batch
from quality_feedback import primary_issue
from run_ui_pipeline import run_pipeline
from update_project_asset_catalog import update_catalog


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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_fingerprint(job: dict[str, Any], run_dir: Path) -> str | None:
    inputs = required_inputs(job, run_dir)
    if not inputs or any(not item["exists"] for item in inputs):
        return None
    digest = hashlib.sha256()
    for item in inputs:
        relative_path = str(item["path"])
        digest.update(relative_path.encode("utf-8"))
        digest.update(file_sha256(run_dir / relative_path).encode("ascii"))
    return digest.hexdigest()


def generation_state(jobs: list[dict[str, Any]], run_dir: Path) -> dict[str, Any]:
    job_states: list[dict[str, Any]] = []
    required_count = 0
    ready_input_count = 0
    for job in jobs:
        inputs = required_inputs(job, run_dir)
        missing = [str(item["path"]) for item in inputs if not item["exists"]]
        fingerprint = candidate_fingerprint(job, run_dir) if not missing else None
        retry = dict(job.get("retry", {}))
        awaiting_fingerprint = retry.get("awaiting_fingerprint")
        target_paths = list(retry.get("target_paths", []))
        awaiting_hashes = dict(retry.get("awaiting_hashes", {}))
        if awaiting_hashes:
            pending_replacements = [
                path for path in target_paths
                if (run_dir / path).is_file() and file_sha256(run_dir / path) == awaiting_hashes.get(path)
            ]
            needs_replacement = bool(pending_replacements)
        else:
            needs_replacement = bool(awaiting_fingerprint and fingerprint == awaiting_fingerprint)
            pending_replacements = target_paths if needs_replacement else []
        required_count += len(inputs)
        ready_input_count += len(inputs) - len(missing)
        job_states.append(
            {
                "id": str(job["id"]),
                "category": str(job["category"]),
                "transparency_mode": str(job.get("transparency_mode", "chroma-key")),
                "expected_count": int(job["expected_count"]),
                "ready": not missing and not needs_replacement,
                "required_inputs": inputs,
                "missing_inputs": missing,
                "pending_replacements": pending_replacements,
                "candidate_fingerprint": fingerprint,
                "retry_candidate_ready": bool(retry and not needs_replacement and not missing),
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
        "pending_replacement_count": sum(len(job["pending_replacements"]) for job in job_states),
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
            "quality_score": None,
            "hard_blocker_count": 0,
            "job_quality": [],
            "style_score": None,
        }
    results = dict(run_summary.get("results", {}))
    return {
        "expected": int(results.get("expected", expected)),
        "exported": int(results.get("exported", 0)),
        "pass": int(results.get("pass", 0)),
        "warning": int(results.get("warning", 0)),
        "fail": int(results.get("fail", 0)),
        "manual_action_required": list(results.get("manual_action_required", [])),
        "quality_score": results.get("quality_score"),
        "hard_blocker_count": int(results.get("hard_blocker_count", 0)),
        "job_quality": list(results.get("job_quality", [])),
        "style_score": results.get("style_score"),
    }


def retry_prompt_source(job: dict[str, Any], target: str) -> str:
    if target == "alpha-matte" and job.get("alpha_matte_prompt_file"):
        return str(job["alpha_matte_prompt_file"])
    return str(job["prompt_file"])


def retry_target_paths(job: dict[str, Any], target: str) -> list[str]:
    if target == "alpha-matte" and job.get("alpha_matte_output"):
        return [str(job["alpha_matte_output"])]
    if target == "native-alpha-provenance" and job.get("provenance_file"):
        return [str(job["provenance_file"])]
    paths = [str(job["generated_output"])]
    if str(job.get("transparency_mode", "chroma-key")) == "model-matte-derived":
        paths.append(str(job["alpha_matte_output"]))
    return paths


def write_regeneration_plan(
    run_dir: Path,
    request: dict[str, Any],
    jobs_payload: dict[str, Any],
    qa_report: dict[str, Any],
) -> dict[str, Any]:
    jobs = list(jobs_payload.get("jobs", []))
    max_attempts = int(request.get("retry_policy", {}).get("max_attempts", 3))
    max_attempts = max(1, min(max_attempts, 5))
    issues_by_job: dict[str, list[dict[str, Any]]] = {str(job["id"]): [] for job in jobs}
    for issue in qa_report.get("issues", []):
        job_id = str(issue.get("job_id", ""))
        if job_id in issues_by_job:
            issues_by_job[job_id].append(dict(issue))
    quality_by_job = {
        str(item["id"]): dict(item)
        for item in qa_report.get("quality", {}).get("jobs", [])
    }
    result_by_job = {str(item["id"]): dict(item) for item in qa_report.get("jobs", [])}
    plan_items: list[dict[str, Any]] = []
    exhausted: list[str] = []

    for job in jobs:
        job_id = str(job["id"])
        fingerprint = candidate_fingerprint(job, run_dir)
        history = list(job.get("candidate_history", []))
        job_has_hard_blocker = any(
            issue.get("severity") == "fail" for issue in issues_by_job[job_id]
        )
        job_ok = bool(result_by_job.get(job_id, {}).get("ok", False)) and not job_has_hard_blocker
        if fingerprint and not any(item.get("fingerprint") == fingerprint for item in history):
            history.append(
                {
                    "attempt": len(history) + 1,
                    "fingerprint": fingerprint,
                    "quality": quality_by_job.get(job_id),
                    "ok": job_ok,
                    "issue_codes": [str(issue.get("code", "unknown")) for issue in issues_by_job[job_id]],
                    "evaluated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        job["candidate_history"] = history
        if job_ok:
            job.pop("retry", None)
            continue

        issue = primary_issue(issues_by_job[job_id])
        if issue is None:
            issue = {
                "code": "unclassified-job-failure",
                "severity": "fail",
                "quality_dimension": "other",
                "quality_penalty": 20,
                "correction_instruction": "Regenerate this job while fixing only the reported QA defect.",
                "retry_target": "production-sheet",
            }
        if len(history) >= max_attempts:
            job["status"] = "failed-retry-exhausted"
            job["retry"] = {
                "status": "exhausted",
                "attempts": len(history),
                "max_attempts": max_attempts,
                "primary_issue": issue,
            }
            exhausted.append(job_id)
            continue

        next_attempt = len(history) + 1
        target = str(issue["retry_target"])
        source_prompt = retry_prompt_source(job, target)
        retry_prompt = f"prompts/{job_id}-retry-{next_attempt:02d}.md"
        original = (run_dir / source_prompt).read_text(encoding="utf-8")
        correction = "\n".join(
            [
                original.rstrip(),
                "",
                f"## V0.13 focused correction attempt {next_attempt}/{max_attempts}",
                "",
                f"Fix exactly this defect: `{issue['code']}`.",
                str(issue["correction_instruction"]),
                "Keep the approved style, ordered resource list, canvas, grid, and every unrelated visual decision unchanged.",
                "Do not combine this retry with unrelated redesigns.",
                "",
            ]
        )
        retry_path = run_dir / retry_prompt
        retry_path.parent.mkdir(parents=True, exist_ok=True)
        retry_path.write_text(correction, encoding="utf-8")
        targets = retry_target_paths(job, target)
        job["status"] = "awaiting-regeneration"
        job["retry"] = {
            "status": "awaiting-regeneration",
            "attempts": len(history),
            "max_attempts": max_attempts,
            "next_attempt": next_attempt,
            "awaiting_fingerprint": fingerprint,
            "awaiting_hashes": {
                path: file_sha256(run_dir / path)
                for path in targets
                if (run_dir / path).is_file()
            },
            "prompt_file": retry_prompt,
            "target_paths": targets,
            "primary_issue": issue,
        }
        plan_items.append(
            {
                "job_id": job_id,
                "category": str(job["category"]),
                "next_attempt": next_attempt,
                "max_attempts": max_attempts,
                "quality": quality_by_job.get(job_id),
                "primary_issue": issue,
                "prompt_file": retry_prompt,
                "replace": targets,
                "input_images": list(job.get("input_images", [])),
            }
        )

    jobs_payload["jobs"] = jobs
    jobs_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(run_dir / "jobs.json", jobs_payload)
    plan = {
        "schema_version": 1,
        "status": "awaiting-regeneration" if plan_items else "failed",
        "max_attempts": max_attempts,
        "items": plan_items,
        "exhausted_jobs": exhausted,
        "hard_gate": "a quality score never overrides fail severity",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(run_dir / "qa" / "regeneration-plan.json", plan)
    lines = ["# V0.13 定向重生成计划", "", f"- 状态：`{plan['status']}`", f"- 最大候选次数：{max_attempts}"]
    for item in plan_items:
        lines.extend(
            [
                "",
                f"## {item['job_id']}",
                "",
                f"- 下一候选：{item['next_attempt']}/{item['max_attempts']}",
                f"- 主缺陷：`{item['primary_issue']['code']}`",
                f"- 纠错 Prompt：`{item['prompt_file']}`",
                f"- 替换文件：{', '.join(f'`{path}`' for path in item['replace'])}",
            ]
        )
    if exhausted:
        lines.extend(["", "## 已耗尽自动候选", "", *[f"- `{job_id}`" for job_id in exhausted]])
    (run_dir / "qa" / "regeneration-plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return plan


def build_summary(
    run_dir: Path,
    request: dict[str, Any],
    generation: dict[str, Any],
    status: str,
    run_summary: dict[str, Any] | None = None,
    retry_plan: dict[str, Any] | None = None,
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
    elif status == "awaiting-regeneration":
        next_actions = [
            "按 qa/regeneration-plan.json 逐项使用纠错 Prompt 生成替代输入。",
            "覆盖计划指定文件后再次运行编排器；未变化的候选不会重复计次。",
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
            "style_consistency": "qa/style-consistency.json" if (run_dir / "qa" / "style-consistency.json").is_file() else None,
            "delivery_summary": "qa/delivery-summary.json",
            "delivery_markdown": "qa/delivery-summary.md",
            "regeneration_plan": "qa/regeneration-plan.json" if (run_dir / "qa" / "regeneration-plan.json").is_file() else None,
        },
        "retry": retry_plan,
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
    if results.get("quality_score") is not None:
        lines.append(
            f"- 质量分：{results['quality_score']}/100；硬阻断：{results['hard_blocker_count']}"
        )
    if results.get("style_score") is not None:
        lines.append(f"- 跨 Sheet 风格一致性：{results['style_score']}/100")
    if summary["missing_inputs"]:
        lines.extend(["", "## 待生成文件", ""])
        lines.extend(f"- `{path}`" for path in summary["missing_inputs"])
    retry = summary.get("retry") or {}
    if retry.get("items"):
        lines.extend(["", "## 定向重生成", ""])
        for item in retry["items"]:
            lines.append(
                f"- `{item['job_id']}`：`{item['primary_issue']['code']}` → `{item['prompt_file']}`"
            )
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


def sync_project_catalog(run_dir: Path, request: dict[str, Any]) -> dict[str, Any] | None:
    manifest = run_dir / "final" / "manifest.json"
    if not manifest.is_file():
        return None
    workspace_root = Path(__file__).resolve().parents[3]
    try:
        run_dir.relative_to(workspace_root / "output")
    except ValueError:
        return None
    project_id = str(request.get("project_id", "game-ui"))
    catalog = workspace_root / "input" / project_id / "ui-asset-catalog.json"
    return update_catalog(catalog, manifest, run_dir.name)


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

    if generation["pending_replacement_count"]:
        retry_plan_path = run_dir / "qa" / "regeneration-plan.json"
        retry_plan = read_json(retry_plan_path) if retry_plan_path.is_file() else None
        summary = build_summary(
            run_dir,
            request,
            generation,
            "awaiting-regeneration",
            existing_run_summary(run_dir),
            retry_plan,
        )
        write_delivery_summary(run_dir, summary)
        return {"ok": True, **summary}

    prior_summary = existing_run_summary(run_dir)
    final_manifest = run_dir / "final" / "manifest.json"
    retry_candidate_ready = any(job["retry_candidate_ready"] for job in generation["jobs"])
    effective_force = bool(force_run or retry_candidate_ready)
    if prior_summary and prior_summary.get("status") == "complete" and final_manifest.is_file() and not effective_force:
        catalog_result = sync_project_catalog(run_dir, request)
        summary = build_summary(run_dir, request, generation, "complete", prior_summary)
        if catalog_result:
            summary["outputs"]["project_asset_catalog"] = (
                Path("..") / ".." / "input" / str(request.get("project_id", "game-ui")) / "ui-asset-catalog.json"
            ).as_posix()
        write_delivery_summary(run_dir, summary)
        return {"ok": True, "reused_existing_delivery": True, **summary}

    if final_manifest.is_file() and not effective_force:
        summary = build_summary(run_dir, request, generation, "failed", prior_summary)
        summary["next_actions"].append("正式 Manifest 已存在；修正后必须使用 --force-run 重跑。")
        write_delivery_summary(run_dir, summary)
        return {"ok": False, **summary}

    result = run_pipeline(
        run_dir,
        transparent_threshold=transparent_threshold,
        opaque_threshold=opaque_threshold,
        adaptive_chroma=adaptive_chroma,
        force=effective_force,
    )
    run_summary = existing_run_summary(run_dir)
    retry_plan = None
    if result["ok"]:
        qa_report = read_json(run_dir / "qa" / "qa-report.json")
        write_regeneration_plan(run_dir, request, read_json(jobs_file), qa_report)
        retry_plan_path = run_dir / "qa" / "regeneration-plan.json"
        if retry_plan_path.is_file():
            retry_plan_path.unlink()
        retry_markdown_path = run_dir / "qa" / "regeneration-plan.md"
        if retry_markdown_path.is_file():
            retry_markdown_path.unlink()
        status = "complete"
    else:
        qa_report = read_json(run_dir / "qa" / "qa-report.json")
        retry_plan = write_regeneration_plan(run_dir, request, read_json(jobs_file), qa_report)
        status = "awaiting-regeneration" if retry_plan["items"] else "failed"
    catalog_result = sync_project_catalog(run_dir, request) if status == "complete" else None
    generation = generation_state(read_json(jobs_file)["jobs"], run_dir)
    summary = build_summary(run_dir, request, generation, status, run_summary, retry_plan)
    if catalog_result:
        summary["outputs"]["project_asset_catalog"] = (
            Path("..") / ".." / "input" / str(request.get("project_id", "game-ui")) / "ui-asset-catalog.json"
        ).as_posix()
    write_delivery_summary(run_dir, summary)
    return {"ok": result["ok"] or status == "awaiting-regeneration", **summary}


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
