#!/usr/bin/env python3
"""Prepare, resume, run, and summarize a complete Codex-first UI asset delivery."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from export_unity_ui import export_unity_ui
from prepare_ui_batch import prepare_batch
from quality_feedback import primary_issue
from quick_source_gate import validate_source_sheet
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
                "generation_sequence": int(job.get("generation_sequence", len(job_states) + 1)),
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


def build_generation_queue(
    jobs: list[dict[str, Any]],
    run_dir: Path,
    policy: dict[str, Any],
) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    for job_index, job in enumerate(jobs, start=1):
        retry = dict(job.get("retry", {}))
        retry_targets = list(retry.get("target_paths", []))
        awaiting_hashes = dict(retry.get("awaiting_hashes", {}))
        for input_index, item in enumerate(required_inputs(job, run_dir), start=1):
            relative_path = str(item["path"])
            pending_replacement = relative_path in retry_targets and (
                not item["exists"]
                or not awaiting_hashes
                or file_sha256(run_dir / relative_path) == awaiting_hashes.get(relative_path)
            )
            prompt_file = item.get("prompt_file")
            if pending_replacement and retry_targets and relative_path == retry_targets[0]:
                prompt_file = retry.get("prompt_file", prompt_file)
            tasks.append(
                {
                    "sequence": len(tasks) + 1,
                    "job_sequence": int(job.get("generation_sequence", job_index)),
                    "job_id": str(job["id"]),
                    "category": str(job["category"]),
                    "input_sequence": input_index,
                    "kind": str(item["kind"]),
                    "path": relative_path,
                    "prompt_file": prompt_file,
                    "input_images": list(item.get("input_images", [])),
                    "edit_source": item.get("edit_source"),
                    "status": "complete" if item["exists"] and not pending_replacement else "pending",
                }
            )
    active_assigned = False
    for task in tasks:
        if task["status"] == "complete":
            continue
        if not active_assigned:
            task["status"] = "active"
            active_assigned = True
        else:
            task["status"] = "blocked"
    active = next((dict(task) for task in tasks if task["status"] == "active"), None)
    return {
        "schema_version": 1,
        "mode": "sequential-inputs",
        "max_concurrent_image_jobs": 1,
        "policy": dict(policy),
        "task_count": len(tasks),
        "complete_count": sum(1 for task in tasks if task["status"] == "complete"),
        "pending_count": sum(1 for task in tasks if task["status"] in {"active", "blocked"}),
        "active_task": active,
        "tasks": tasks,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_generation_queue(run_dir: Path, queue: dict[str, Any]) -> None:
    write_json(run_dir / "qa" / "generation-queue.json", queue)
    lines = [
        "# 逐张图片生成队列",
        "",
        "- 模式：`sequential-inputs`",
        "- 最大并发图片 Job：`1`",
        f"- 进度：{queue['complete_count']}/{queue['task_count']}",
    ]
    active = queue.get("active_task")
    if active:
        lines.extend(
            [
                "",
                "## 当前唯一任务",
                "",
                f"- Job：`{active['job_id']}`",
                f"- 类型：`{active['kind']}`",
                f"- 输出：`{active['path']}`",
                f"- Prompt：`{active['prompt_file']}`" if active.get("prompt_file") else "- Prompt：来源侧车校验",
                "- 完成当前文件后重新运行编排器，再激活下一项。",
            ]
        )
    else:
        lines.extend(["", "- 队列已完成。"])
    (run_dir / "qa" / "generation-queue.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def attach_generation_queue(
    generation: dict[str, Any],
    jobs: list[dict[str, Any]],
    request: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    policy = dict(
        request.get(
            "generation_policy",
            {
                "mode": "sequential-inputs",
                "max_concurrent_image_jobs": 1,
                "rerun_orchestrator_after_each_input": True,
            },
        )
    )
    queue = build_generation_queue(jobs, run_dir, policy)
    write_generation_queue(run_dir, queue)
    generation["policy"] = policy
    generation["queue"] = "qa/generation-queue.json"
    generation["next_task"] = queue["active_task"]
    return generation


def existing_run_summary(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "qa" / "run-summary.json"
    return read_json(path) if path.is_file() else None


def generation_budget_state(
    request: dict[str, Any],
    jobs: list[dict[str, Any]],
    jobs_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = dict(request.get("generation_budget", {}))
    max_extra_calls = max(0, min(int(raw.get("max_extra_calls", 1)), 5))
    minutes = list(raw.get("estimated_minutes_per_call", [5, 8]))
    low, high = float(minutes[0]), float(minutes[1])
    initial_calls = sum(
        1
        for job in jobs
        for item in required_inputs(job, Path("."))
        if item["kind"] in {"production-sheet", "alpha-matte"}
    )
    persisted = dict((jobs_payload or {}).get("generation_budget", {}))
    committed = max(0, int(persisted.get("extra_calls_committed", 0)))
    remaining = max(0, max_extra_calls - committed)
    return {
        "initial_image_calls": initial_calls,
        "max_extra_calls": max_extra_calls,
        "extra_calls_committed": committed,
        "extra_calls_remaining": remaining,
        "call_budget_range": [initial_calls, initial_calls + max_extra_calls],
        "estimated_minutes_per_call": [low, high],
        "estimated_minutes_without_retry": [round(initial_calls * low, 1), round(initial_calls * high, 1)],
        "estimated_minutes_with_budget": [round(initial_calls * low, 1), round((initial_calls + max_extra_calls) * high, 1)],
    }


def run_quick_source_gates(
    run_dir: Path,
    jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    reports = [validate_source_sheet(job, run_dir) for job in jobs]
    issues: list[dict[str, Any]] = []
    for job, report in zip(jobs, reports):
        for issue in report.get("issues", []):
            issues.append({**dict(issue), "severity": "fail", "job_id": str(job["id"])})
    summary = {
        "schema_version": 1,
        "ok": not issues,
        "status": "pass" if not issues else "failed",
        "job_count": len(jobs),
        "passed_job_count": sum(1 for report in reports if report.get("ok")),
        "failed_job_count": sum(1 for report in reports if not report.get("ok")),
        "issues": issues,
        "reports": [f"qa/source-gates/{job['id']}.json" for job in jobs],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(run_dir / "qa" / "source-gate-summary.json", summary)
    return summary


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
    budget_exhausted: list[str] = []
    budget = generation_budget_state(request, jobs, jobs_payload)
    extra_calls_committed = int(budget["extra_calls_committed"])
    extra_calls_remaining = int(budget["extra_calls_remaining"])

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
        required_calls = sum(1 for path in targets if str(path).lower().endswith(".png"))
        if required_calls > extra_calls_remaining:
            retry_path.unlink(missing_ok=True)
            job["status"] = "failed-generation-budget-exhausted"
            job["retry"] = {
                "status": "generation-budget-exhausted",
                "attempts": len(history),
                "max_attempts": max_attempts,
                "required_extra_calls": required_calls,
                "remaining_extra_calls": extra_calls_remaining,
                "primary_issue": issue,
            }
            budget_exhausted.append(job_id)
            continue
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
            "planned_extra_calls": required_calls,
        }
        extra_calls_committed += required_calls
        extra_calls_remaining -= required_calls
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
                "planned_extra_calls": required_calls,
            }
        )

    jobs_payload["generation_budget"] = {
        "max_extra_calls": int(budget["max_extra_calls"]),
        "extra_calls_committed": extra_calls_committed,
        "extra_calls_remaining": extra_calls_remaining,
    }
    jobs_payload["jobs"] = jobs
    jobs_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(run_dir / "jobs.json", jobs_payload)
    plan = {
        "schema_version": 1,
        "status": "awaiting-regeneration" if plan_items else "failed",
        "max_attempts": max_attempts,
        "items": plan_items,
        "exhausted_jobs": exhausted,
        "budget_exhausted_jobs": budget_exhausted,
        "generation_budget": generation_budget_state(request, jobs, jobs_payload),
        "hard_gate": "a quality score never overrides fail severity",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(run_dir / "qa" / "regeneration-plan.json", plan)
    lines = [
        "# V0.13 定向重生成计划",
        "",
        f"- 状态：`{plan['status']}`",
        f"- 最大候选次数：{max_attempts}",
        f"- 全局额外生图预算：{plan['generation_budget']['extra_calls_committed']}/{plan['generation_budget']['max_extra_calls']}",
    ]
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
    if budget_exhausted:
        lines.extend(["", "## 已耗尽全局额外生图预算", "", *[f"- `{job_id}`" for job_id in budget_exhausted]])
    (run_dir / "qa" / "regeneration-plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return plan


def existing_delivery_summary(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "qa" / "delivery-summary.json"
    return read_json(path) if path.is_file() else None


def resolve_run_relative(run_dir: Path, value: str, label: str) -> Path:
    candidate = (run_dir / value).resolve()
    try:
        candidate.relative_to(run_dir)
    except ValueError as error:
        raise ValueError(f"{label} must stay inside the run directory: {value}") from error
    return candidate


def unity_delivery_state(run_dir: Path, request: dict[str, Any]) -> dict[str, Any]:
    config = dict(request.get("unity_delivery", {}))
    if not bool(config.get("enabled", False)):
        return {"enabled": False, "status": "not-requested", "screen_count": 0, "screens": []}
    layout_relative = str(config.get("layout", "unity/unity-layout.json"))
    try:
        layout_path = resolve_run_relative(run_dir, layout_relative, "unity_delivery.layout")
    except ValueError as error:
        return {
            "enabled": True,
            "status": "configuration-invalid",
            "screen_count": 0,
            "screens": [],
            "error": str(error),
        }
    if not layout_path.is_file():
        return {
            "enabled": True,
            "status": "configuration-invalid",
            "screen_count": 0,
            "screens": [],
            "error": f"Unity layout not found: {layout_relative}",
        }
    layout = read_json(layout_path)
    screens = [str(screen.get("id", "")) for screen in layout.get("screens", [])]
    report_path = run_dir / "unity" / "unity-import-report.json"
    report = read_json(report_path) if report_path.is_file() else None
    status = "complete" if report and bool(report.get("ok")) else "pending"
    previews_dir = run_dir / "unity" / "previews"
    previews = [path.relative_to(run_dir).as_posix() for path in sorted(previews_dir.glob("*.png"))]
    return {
        "enabled": True,
        "status": status,
        "screen_count": len(screens),
        "screens": screens,
        "layout": layout_relative,
        "outputs": {
            "preflight": "unity/unity-preflight.json",
            "plan": "unity/unity-import-plan.json",
            "report": "unity/unity-import-report.json",
            "log": "unity/unity-batch.log",
            "rollback": "unity/unity-rollback.json",
            "previews_directory": "unity/previews",
            "previews": previews,
        },
    }


def execute_unity_delivery(
    run_dir: Path,
    request: dict[str, Any],
    force: bool = False,
) -> dict[str, Any]:
    state = unity_delivery_state(run_dir, request)
    if not state["enabled"] or state["status"] == "configuration-invalid":
        return state
    prior_delivery = existing_delivery_summary(run_dir)
    if (
        not force
        and state["status"] == "complete"
        and prior_delivery
        and prior_delivery.get("status") == "complete"
    ):
        return {**state, "reused_existing_unity": True}
    config = dict(request["unity_delivery"])
    try:
        result = export_unity_ui(
            run_dir,
            Path(str(config["unity_project"])),
            Path(str(config["unity_editor"])),
            resolve_run_relative(run_dir, str(config["layout"]), "unity_delivery.layout"),
            Path(__file__).resolve().parents[1] / "assets" / "unity-package",
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        return {**state, "status": "unity-failed", "ok": False, "error": str(error)}
    refreshed = unity_delivery_state(run_dir, request)
    return {
        **refreshed,
        "status": "complete" if result.get("ok") else str(result.get("status", "unity-failed")),
        "ok": bool(result.get("ok")),
        "returncode": result.get("returncode"),
        "results": dict(result.get("results", {})),
    }


def build_summary(
    run_dir: Path,
    request: dict[str, Any],
    generation: dict[str, Any],
    status: str,
    run_summary: dict[str, Any] | None = None,
    retry_plan: dict[str, Any] | None = None,
    unity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generation = {"method": str(request.get("generation_method", "built-in-imagegen")), **generation}
    jobs_payload = read_json(run_dir / "jobs.json") if (run_dir / "jobs.json").is_file() else {"jobs": []}
    generation["budget"] = generation_budget_state(request, list(jobs_payload.get("jobs", [])), jobs_payload)
    results = delivery_results(run_summary, int(request.get("expected_count", 0)))
    missing = [
        path
        for job in generation["jobs"]
        for path in job["missing_inputs"]
    ]
    unity = unity or unity_delivery_state(run_dir, request)
    if status == "awaiting-generation":
        active = generation.get("next_task")
        next_actions = (
            [
                f"只生成当前激活输入 {active['path']}，不要并行生成后续图片。",
                "保存后立即再次运行编排器，由队列激活下一项。",
            ]
            if active
            else ["再次运行编排器刷新逐张生成队列。"]
        )
    elif status == "awaiting-regeneration":
        next_actions = [
            "按 qa/regeneration-plan.json 逐项使用纠错 Prompt 生成替代输入。",
            "覆盖计划指定文件后再次运行编排器；未变化的候选不会重复计次。",
        ]
    elif status == "complete":
        next_actions = ["检查资源 Contact Sheet，以及每个 Screen 的 Unity 渲染预览。"] if unity["enabled"] else [
            "交付资源包前人工检查 qa/contact-sheet.png。"
        ]
    elif status.startswith("unity-") or status == "configuration-invalid":
        next_actions = [
            "检查 Unity 预检、导入报告和 batchmode 日志。",
            "修正目标工程、Editor 或显式布局后，使用 --force-unity 续跑；不会重新生成图片。",
        ]
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
            "generation_queue": "qa/generation-queue.json",
            "source_gate": "qa/source-gate-summary.json" if (run_dir / "qa" / "source-gate-summary.json").is_file() else None,
            "regeneration_plan": "qa/regeneration-plan.json" if (run_dir / "qa" / "regeneration-plan.json").is_file() else None,
        },
        "retry": retry_plan,
        "unity": unity,
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
    budget = generation.get("budget", {})
    if budget:
        lines.extend(
            [
                f"- 首轮生图调用：{budget['initial_image_calls']}",
                f"- 全局额外调用预算：{budget['extra_calls_committed']}/{budget['max_extra_calls']}",
                f"- 预计生图时长：{budget['estimated_minutes_with_budget'][0]}–{budget['estimated_minutes_with_budget'][1]} 分钟",
            ]
        )
    if results.get("quality_score") is not None:
        lines.append(
            f"- 质量分：{results['quality_score']}/100；硬阻断：{results['hard_blocker_count']}"
        )
    if results.get("style_score") is not None:
        lines.append(f"- 跨 Sheet 风格一致性：{results['style_score']}/100")
    if summary["missing_inputs"]:
        lines.extend(["", "## 待生成文件", ""])
        lines.extend(f"- `{path}`" for path in summary["missing_inputs"])
    active = generation.get("next_task")
    if active:
        lines.extend(
            [
                "",
                "## 当前唯一生成任务",
                "",
                f"- `{active['job_id']}` / `{active['kind']}` → `{active['path']}`",
            ]
        )
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
    unity = summary.get("unity") or {}
    if unity.get("enabled"):
        lines.extend(
            [
                "",
                "## Unity 多屏交付",
                "",
                f"- 状态：`{unity.get('status')}`",
                f"- Screen：{unity.get('screen_count', 0)}",
            ]
        )
        lines.extend(f"- `{screen}`" for screen in unity.get("screens", []))
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


def finalize_completed_assets(
    run_dir: Path,
    request: dict[str, Any],
    generation: dict[str, Any],
    run_summary: dict[str, Any],
    force_unity: bool = False,
    reused_assets: bool = False,
) -> dict[str, Any]:
    catalog_result = sync_project_catalog(run_dir, request)
    unity = execute_unity_delivery(run_dir, request, force=force_unity)
    if unity["enabled"] and unity.get("status") != "complete":
        status = str(unity.get("status", "unity-failed"))
        if not status.startswith("unity-") and status != "configuration-invalid":
            status = "unity-failed"
    else:
        status = "complete"
    summary = build_summary(run_dir, request, generation, status, run_summary, unity=unity)
    if catalog_result:
        summary["outputs"]["project_asset_catalog"] = (
            Path("..") / ".." / "input" / str(request.get("project_id", "game-ui")) / "ui-asset-catalog.json"
        ).as_posix()
    write_delivery_summary(run_dir, summary)
    return {
        "ok": status == "complete",
        "reused_existing_delivery": bool(
            reused_assets and (not unity["enabled"] or unity.get("reused_existing_unity"))
        ),
        **summary,
    }


def orchestrate(
    run_dir: Path,
    request_path: Path | None = None,
    force_run: bool = False,
    transparent_threshold: float = 12.0,
    opaque_threshold: float = 96.0,
    adaptive_chroma: bool = True,
    force_unity: bool = False,
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
    generation = attach_generation_queue(generation, jobs, request, run_dir)

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
        return finalize_completed_assets(
            run_dir,
            request,
            generation,
            prior_summary,
            force_unity=force_unity,
            reused_assets=True,
        )

    if final_manifest.is_file() and not effective_force:
        summary = build_summary(run_dir, request, generation, "failed", prior_summary)
        summary["next_actions"].append("正式 Manifest 已存在；修正后必须使用 --force-run 重跑。")
        write_delivery_summary(run_dir, summary)
        return {"ok": False, **summary}

    source_gate = run_quick_source_gates(run_dir, jobs)
    if not source_gate["ok"]:
        gate_qa = {
            "jobs": [
                {
                    "id": str(job["id"]),
                    "ok": not any(issue["job_id"] == str(job["id"]) for issue in source_gate["issues"]),
                }
                for job in jobs
            ],
            "issues": source_gate["issues"],
            "quality": {"jobs": []},
        }
        retry_plan = write_regeneration_plan(run_dir, request, read_json(jobs_file), gate_qa)
        status = "awaiting-regeneration" if retry_plan["items"] else "failed"
        refreshed_jobs = read_json(jobs_file)["jobs"]
        generation = attach_generation_queue(
            generation_state(refreshed_jobs, run_dir), refreshed_jobs, request, run_dir
        )
        summary = build_summary(run_dir, request, generation, status, prior_summary, retry_plan)
        write_delivery_summary(run_dir, summary)
        return {"ok": status == "awaiting-regeneration", **summary}

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
        status = "assets-complete"
    else:
        qa_report = read_json(run_dir / "qa" / "qa-report.json")
        retry_plan = write_regeneration_plan(run_dir, request, read_json(jobs_file), qa_report)
        status = "awaiting-regeneration" if retry_plan["items"] else "failed"
    refreshed_jobs = read_json(jobs_file)["jobs"]
    generation = attach_generation_queue(generation_state(refreshed_jobs, run_dir), refreshed_jobs, request, run_dir)
    if status == "assets-complete":
        return finalize_completed_assets(
            run_dir,
            request,
            generation,
            run_summary or {},
            force_unity=bool(force_unity or effective_force),
        )
    summary = build_summary(run_dir, request, generation, status, run_summary, retry_plan)
    write_delivery_summary(run_dir, summary)
    return {"ok": result["ok"] or status == "awaiting-regeneration", **summary}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--request", type=Path, help="Batch request JSON; required only for a new run")
    parser.add_argument("--force-run", action="store_true", help="Rerun deterministic processing")
    parser.add_argument("--force-unity", action="store_true", help="Rerun Unity export without regenerating images")
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
        force_unity=args.force_unity,
    )
    print(json.dumps(result, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
