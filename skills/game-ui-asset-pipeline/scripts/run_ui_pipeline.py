#!/usr/bin/env python3
"""Run deterministic post-processing for every generated sheet in a prepared UI run."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from apply_alpha_matte import apply_alpha_matte, sha256_file as sha256_matte_file
from extract_sheet_assets import extract_assets
from make_contact_sheet import make_contact_sheet
from native_alpha import validate_native_alpha_source
from normalize_assets import normalize_manifest_assets, resize_rgba_premultiplied
from remove_chroma_key import parse_hex_color, recommend_chroma_thresholds, remove_chroma
from validate_asset_pack import validate_pack


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_existing_alpha(image: Image.Image) -> tuple[Image.Image, dict[str, Any]]:
    array = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    transparent = array[:, :, 3] == 0
    hidden_rgb_cleaned = int(np.count_nonzero(np.any(array[:, :, :3][transparent] != 0, axis=1)))
    array[:, :, :3][transparent] = 0
    cleaned = Image.fromarray(array, mode="RGBA")
    return cleaned, {
        "schema_version": 1,
        "ok": bool(np.any(array[:, :, 3] > 0)),
        "algorithm": "existing-alpha-hidden-rgb-cleanup",
        "width": cleaned.width,
        "height": cleaned.height,
        "transparent_pixels": int(np.count_nonzero(transparent)),
        "hidden_rgb_cleaned_pixels": hidden_rgb_cleaned,
        "partial_alpha_pixels": int(np.count_nonzero((array[:, :, 3] > 0) & (array[:, :, 3] < 255))),
        "opaque_pixels": int(np.count_nonzero(array[:, :, 3] == 255)),
    }


def relative(path: Path, root: Path) -> str:
    return path.expanduser().resolve().relative_to(root.expanduser().resolve()).as_posix()


def run_pipeline(
    run_dir: Path,
    transparent_threshold: float = 12.0,
    opaque_threshold: float = 96.0,
    adaptive_chroma: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    run_dir = run_dir.expanduser().resolve()
    request_path = run_dir / "request.json"
    jobs_path = run_dir / "jobs.json"
    request = read_json(request_path)
    jobs_payload = read_json(jobs_path)
    jobs = jobs_payload.get("jobs", [])
    if not jobs:
        raise ValueError("jobs.json contains no jobs")
    final_manifest_path = run_dir / "final" / "manifest.json"
    if final_manifest_path.exists() and not force:
        raise FileExistsError(f"final manifest already exists: {final_manifest_path}; use --force to rerun")

    missing = [job["generated_output"] for job in jobs if not (run_dir / job["generated_output"]).is_file()]
    missing.extend(
        str(job["alpha_matte_output"])
        for job in jobs
        if str(job.get("transparency_mode", "chroma-key")) == "model-matte-derived"
        and not (run_dir / str(job.get("alpha_matte_output", ""))).is_file()
    )
    if missing:
        raise FileNotFoundError("missing generated sheets: " + ", ".join(missing))

    native_reports: dict[str, dict[str, Any]] = {}
    native_failures: list[dict[str, Any]] = []
    matte_reports: dict[str, dict[str, Any]] = {}
    for job in jobs:
        if str(job.get("transparency_mode", "chroma-key")) != "native-alpha-required":
            continue
        job_id = str(job["id"])
        provenance_value = job.get("provenance_file")
        provenance_path = run_dir / str(provenance_value or f"generated/{job_id}.provenance.json")
        report = validate_native_alpha_source(
            run_dir / job["generated_output"], provenance_path, str(job["generated_output"])
        )
        native_reports[job_id] = report
        report_path = run_dir / "qa" / f"{job_id}-native-alpha.json"
        write_json(report_path, report)
        job.setdefault("reports", {})["native_alpha"] = relative(report_path, run_dir)
        if not report["ok"]:
            job["status"] = "failed-native-alpha-preflight"
            native_failures.extend({"job_id": job_id, **issue} for issue in report["issues"])
    matte_failures: list[dict[str, Any]] = []
    for job in jobs:
        if str(job.get("transparency_mode", "chroma-key")) != "model-matte-derived":
            continue
        job_id = str(job["id"])
        generated_path = run_dir / str(job["generated_output"])
        matte_path = run_dir / str(job["alpha_matte_output"])
        with Image.open(generated_path) as opened_source, Image.open(matte_path) as opened_matte:
            _preview, report = apply_alpha_matte(opened_source, opened_matte)
        report.update(
            {
                "source": relative(generated_path, run_dir),
                "source_sha256": sha256_matte_file(generated_path),
                "alpha_matte": relative(matte_path, run_dir),
                "alpha_matte_sha256": sha256_matte_file(matte_path),
                "generation_method": request.get("generation_method", "built-in-imagegen"),
            }
        )
        matte_reports[job_id] = report
        report_path = run_dir / "qa" / f"{job_id}-alpha-matte.json"
        write_json(report_path, report)
        job.setdefault("reports", {})["alpha_matte"] = relative(report_path, run_dir)
        if not report["ok"]:
            job["status"] = "failed-alpha-matte-preflight"
            matte_failures.extend({"job_id": job_id, **issue} for issue in report["issues"])
    preflight_failures = native_failures + matte_failures
    if preflight_failures:
        jobs_payload["jobs"] = jobs
        jobs_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_json(jobs_path, jobs_payload)
        qa_report = {
            "schema_version": 3,
            "ok": False,
            "expected_count": int(request.get("expected_count", 0)),
            "manifest_count": 0,
            "valid_assets": 0,
            "pass_count": 0,
            "warning_count": 0,
            "fail_count": len(preflight_failures),
            "issues": preflight_failures,
            "jobs": [{"id": str(job["id"]), "ok": False} for job in jobs],
            "manual_action_required": sorted({str(issue["job_id"]) for issue in preflight_failures}),
        }
        qa_report_path = run_dir / "qa" / "qa-report.json"
        write_json(qa_report_path, qa_report)
        run_summary = {
            "schema_version": 3,
            "project_id": request.get("project_id", "game-ui"),
            "status": "failed-transparency-preflight",
            "generation": {
                "method": request.get("generation_method", "unknown"),
                "sheet_count": len(jobs),
                "native_alpha_required_count": len(native_reports),
                "native_alpha_verified_count": sum(1 for report in native_reports.values() if report["ok"]),
                "model_matte_required_count": len(matte_reports),
                "model_matte_verified_count": sum(1 for report in matte_reports.values() if report["ok"]),
            },
            "pipeline": {"manifest": None, "contact_sheet": None, "qa_report": relative(qa_report_path, run_dir)},
            "results": {
                "expected": int(request.get("expected_count", 0)),
                "exported": 0,
                "pass": 0,
                "warning": 0,
                "fail": len(preflight_failures),
                "manual_action_required": qa_report["manual_action_required"],
            },
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json(run_dir / "qa" / "run-summary.json", run_summary)
        return {"ok": False, "run_dir": str(run_dir), **run_summary["results"]}

    all_entries: list[dict[str, Any]] = []
    all_issues: list[dict[str, Any]] = []
    job_results: list[dict[str, Any]] = []
    fragment_policies: dict[str, dict[str, Any]] = {}
    for job in jobs:
        job_id = str(job["id"])
        job_request = read_json(run_dir / job.get("request_file", "request.json"))
        layout = read_json(run_dir / job["layout_json"])
        generated_path = run_dir / job["generated_output"]
        with Image.open(generated_path) as opened:
            source_original = opened.copy()
        source = source_original.convert("RGBA")
        source_size = [source.width, source.height]
        expected_size = tuple(int(value) for value in job_request.get("canvas", source_size))
        resized = source.size != expected_size
        if resized:
            source = resize_rgba_premultiplied(source, expected_size)

        transparency_mode = str(job.get("transparency_mode", job_request.get("transparency_mode", "auto")))
        native_report = native_reports.get(job_id)
        matte_report = matte_reports.get(job_id)
        alpha_min, _alpha_max = source.getchannel("A").getextrema()
        if transparency_mode == "model-matte-derived":
            matte_path = run_dir / str(job["alpha_matte_output"])
            with Image.open(matte_path) as opened_matte:
                alpha_sheet, regenerated_report = apply_alpha_matte(source_original, opened_matte)
            background_report = dict(matte_report or regenerated_report)
            if alpha_sheet.size != expected_size:
                alpha_sheet = resize_rgba_premultiplied(alpha_sheet, expected_size)
            background_report.update(
                {
                    "model_matte_verified": True,
                    "alpha_matte_input": relative(matte_path, run_dir),
                }
            )
            background_mode = "model-matte-derived"
        elif transparency_mode == "native-alpha-required":
            alpha_sheet, background_report = clean_existing_alpha(source)
            background_report.update(
                {
                    "algorithm": "native-alpha-preserve-hidden-rgb-cleanup",
                    "native_alpha_verified": True,
                    "source_sha256": native_report["source_sha256"] if native_report else None,
                    "provenance_file": relative(
                        run_dir / str(job["provenance_file"]), run_dir
                    ),
                    "source_alpha": native_report["alpha"] if native_report else None,
                }
            )
            background_mode = "native-alpha"
        elif alpha_min < 255:
            alpha_sheet, background_report = clean_existing_alpha(source)
            background_mode = "existing-alpha"
        else:
            key = parse_hex_color(str(job_request["chroma_key"]))
            diagnostics = recommend_chroma_thresholds(source, key)
            selected_transparent = transparent_threshold
            selected_opaque = opaque_threshold
            adaptive_applied = bool(adaptive_chroma and diagnostics["auto_apply"])
            if adaptive_applied:
                selected_transparent = float(diagnostics["suggested_transparent_threshold"])
                selected_opaque = float(diagnostics["suggested_opaque_threshold"])
            alpha_sheet, background_report = remove_chroma(
                source,
                key,
                transparent_threshold=selected_transparent,
                opaque_threshold=selected_opaque,
            )
            background_report.update(
                {
                    "adaptive_thresholds_requested": adaptive_chroma,
                    "adaptive_thresholds_applied": adaptive_applied,
                    "threshold_diagnostics": diagnostics,
                }
            )
            if adaptive_chroma and not diagnostics["auto_apply"]:
                background_report["ok"] = False
            background_mode = "chroma-key"
        alpha_path = run_dir / "extracted" / f"{job_id}-alpha.png"
        alpha_path.parent.mkdir(parents=True, exist_ok=True)
        alpha_sheet.save(alpha_path, format="PNG")
        background_report.update(
            {
                "input": relative(generated_path, run_dir),
                "output": relative(alpha_path, run_dir),
                "source_size": source_size,
                "processing_size": list(expected_size),
                "resized": resized,
                "background_mode": background_mode,
            }
        )
        background_report_path = run_dir / "qa" / f"{job_id}-background.json"
        write_json(background_report_path, background_report)

        extracted_dir = run_dir / "extracted" / job_id / "assets"
        extracted_manifest, extraction_report = extract_assets(
            alpha_sheet,
            layout,
            job_request,
            extracted_dir,
        )
        extracted_manifest["source_sheet"] = relative(generated_path, run_dir)
        fragment_policies[str(job["category"])] = dict(extracted_manifest["fragment_policy"])
        extracted_manifest_path = run_dir / "extracted" / f"{job_id}-manifest.json"
        extraction_report_path = run_dir / "qa" / f"{job_id}-extract.json"
        write_json(extracted_manifest_path, extracted_manifest)
        write_json(extraction_report_path, extraction_report)

        final_dir = run_dir / "final" / str(job["category"])
        normalized_manifest = normalize_manifest_assets(
            extracted_manifest,
            job_request,
            extracted_dir,
            final_dir,
        )
        for entry in normalized_manifest.get("assets", []):
            entry["source_sheet"] = relative(generated_path, run_dir)
            entry["output"] = relative(final_dir / Path(entry["output"]).name, run_dir)
            entry["padding"] = int(job_request.get("padding", 8))
            entry["alignment"] = str(job_request.get("alignment", "center"))
            entry["pivot"] = [0.5, 0.0] if entry["alignment"] == "bottom-center" else [0.5, 0.5]
            entry["chroma_key"] = job_request.get("chroma_key") if background_mode == "chroma-key" else None
            entry["transparency_mode"] = transparency_mode
            entry["alpha_origin"] = (
                "model-native" if background_mode == "native-alpha" else
                "gpt-image-2-matte-derived" if background_mode == "model-matte-derived" else
                "chroma-derived" if background_mode == "chroma-key" else
                "existing-alpha-unverified"
            )
            if background_mode == "native-alpha" and native_report:
                entry["source_sha256"] = native_report["source_sha256"]
                entry["alpha_provenance"] = relative(run_dir / str(job["provenance_file"]), run_dir)
            if background_mode == "model-matte-derived" and matte_report:
                entry["source_sha256"] = matte_report["source_sha256"]
                entry["alpha_matte"] = matte_report["alpha_matte"]
                entry["alpha_matte_sha256"] = matte_report["alpha_matte_sha256"]
            all_entries.append(entry)
        normalized_manifest_path = run_dir / "normalized" / f"{job_id}-manifest.json"
        write_json(normalized_manifest_path, normalized_manifest)

        job_issues = []
        entries_by_source_index = {
            int(entry["source_index"]): entry for entry in normalized_manifest.get("assets", [])
        }
        for issue in extraction_report.get("issues", []):
            enriched = {"job_id": job_id, **issue}
            source_index = issue.get("source_index")
            if isinstance(source_index, int) and source_index in entries_by_source_index:
                enriched["asset_id"] = entries_by_source_index[source_index]["id"]
            job_issues.append(enriched)
        threshold_issues = background_report.get("threshold_diagnostics", {}).get("issues", [])
        for issue in threshold_issues:
            job_issues.append({"job_id": job_id, **issue})
        if not background_report.get("ok", False) and not any(
            issue.get("severity") == "fail" for issue in threshold_issues
        ):
            job_issues.append({"job_id": job_id, "severity": "fail", "code": "background-cleanup-failed"})
        all_issues.extend(job_issues)
        job_ok = bool(background_report.get("ok", False) and extraction_report.get("ok", False))
        job["status"] = "processed" if job_ok else "failed"
        job["reports"] = {
            "background": relative(background_report_path, run_dir),
            "extraction": relative(extraction_report_path, run_dir),
            "normalized_manifest": relative(normalized_manifest_path, run_dir),
            **({"native_alpha": f"qa/{job_id}-native-alpha.json"} if native_report else {}),
            **({"alpha_matte": f"qa/{job_id}-alpha-matte.json"} if matte_report else {}),
        }
        job_results.append(
            {
                "id": job_id,
                "ok": job_ok,
                "expected_count": int(job["expected_count"]),
                "exported_count": int(normalized_manifest.get("exported_count", 0)),
            }
        )

    supplemental_manifest_path = run_dir / "supplemental-manifest.json"
    supplemental_entries: list[dict[str, Any]] = []
    if supplemental_manifest_path.is_file():
        supplemental_payload = read_json(supplemental_manifest_path)
        supplemental_entries = list(supplemental_payload.get("assets", []))
        existing_ids = {str(entry["id"]) for entry in all_entries}
        for entry_index, entry in enumerate(supplemental_entries):
            asset_id = str(entry.get("id", ""))
            output = str(entry.get("output", ""))
            if not asset_id or asset_id in existing_ids:
                raise ValueError(f"invalid or duplicate supplemental asset id at index {entry_index}: {asset_id}")
            output_path = (run_dir / output).resolve()
            try:
                output_path.relative_to((run_dir / "final").resolve())
            except ValueError as error:
                raise ValueError(f"supplemental asset output must stay under final/: {output}") from error
            if not output_path.is_file():
                raise FileNotFoundError(f"supplemental asset output missing: {output_path}")
            existing_ids.add(asset_id)
        all_entries.extend(supplemental_entries)

    all_entries.sort(key=lambda entry: (str(entry["id"])[:2], int(entry.get("category_index", 0))))
    final_manifest = {
        "schema_version": 3,
        "project_id": request.get("project_id", "game-ui"),
        "stage": "final",
        "expected_count": int(request.get("expected_count", len(all_entries))),
        "exported_count": len(all_entries),
        "fragment_policies": fragment_policies,
        "native_alpha_verified_sheets": len(native_reports),
        "model_matte_verified_sheets": len(matte_reports),
        "supplemental_asset_count": len(supplemental_entries),
        "assets": all_entries,
    }
    write_json(final_manifest_path, final_manifest)
    contact_path = run_dir / "qa" / "contact-sheet.png"
    contact_report = make_contact_sheet(final_manifest, run_dir, contact_path)
    validation = validate_pack(final_manifest, run_dir, request, strict_files=True)
    all_issues.extend(validation.get("issues", []))
    failures = [issue for issue in all_issues if issue.get("severity") == "fail"]
    warnings = [issue for issue in all_issues if issue.get("severity") == "warning"]
    output_to_id = {str(entry.get("output", "")): str(entry["id"]) for entry in all_entries}
    warned_assets = {
        str(issue.get("asset_id") or output_to_id.get(str(issue.get("file", "")), ""))
        for issue in warnings
        if issue.get("asset_id") or output_to_id.get(str(issue.get("file", "")))
    }
    qa_report = {
        "schema_version": 3,
        "ok": not failures and validation.get("ok", False) and contact_report.get("ok", False),
        "expected_count": final_manifest["expected_count"],
        "manifest_count": len(all_entries),
        "valid_assets": validation.get("valid_assets", 0),
        "pass_count": max(0, len(all_entries) - len(warned_assets)),
        "warning_count": len(warnings),
        "fail_count": len(failures),
        "issues": all_issues,
        "jobs": job_results,
        "manual_action_required": sorted(
            {str(issue.get("asset_id") or issue.get("job_id") or issue.get("file") or issue.get("code")) for issue in failures}
        ),
    }
    qa_report_path = run_dir / "qa" / "qa-report.json"
    write_json(qa_report_path, qa_report)
    jobs_payload["jobs"] = jobs
    jobs_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(jobs_path, jobs_payload)
    run_summary = {
        "schema_version": 3,
        "project_id": request.get("project_id", "game-ui"),
        "status": "complete" if qa_report["ok"] else "failed",
        "generation": {
            "method": request.get("generation_method", "built-in-imagegen"),
            "sheet_count": len(jobs),
            "native_alpha_required_count": len(native_reports),
            "native_alpha_verified_count": sum(1 for report in native_reports.values() if report["ok"]),
            "model_matte_required_count": len(matte_reports),
            "model_matte_verified_count": sum(1 for report in matte_reports.values() if report["ok"]),
        },
        "pipeline": {
            "manifest": relative(final_manifest_path, run_dir),
            "contact_sheet": relative(contact_path, run_dir),
            "qa_report": relative(qa_report_path, run_dir),
        },
        "results": {
            "expected": final_manifest["expected_count"],
            "exported": len(all_entries),
            "pass": qa_report["pass_count"],
            "warning": qa_report["warning_count"],
            "fail": qa_report["fail_count"],
            "manual_action_required": qa_report["manual_action_required"],
        },
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    run_summary_path = run_dir / "qa" / "run-summary.json"
    write_json(run_summary_path, run_summary)
    return {"ok": qa_report["ok"], "run_dir": str(run_dir), **run_summary["results"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--transparent-threshold", type=float, default=12.0)
    parser.add_argument("--opaque-threshold", type=float, default=96.0)
    parser.add_argument("--fixed-chroma-thresholds", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.opaque_threshold <= args.transparent_threshold:
        parser.error("opaque-threshold must be greater than transparent-threshold")
    result = run_pipeline(
        args.run_dir,
        transparent_threshold=args.transparent_threshold,
        opaque_threshold=args.opaque_threshold,
        adaptive_chroma=not args.fixed_chroma_thresholds,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False))
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
