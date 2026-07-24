import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image, ImageDraw


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def load_module(name: str):
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ORCHESTRATOR = load_module("orchestrate_ui_delivery")


class P6OrchestrationTest(unittest.TestCase):
    def request(self) -> dict:
        return {
            "project_id": "p6-mixed-delivery",
            "style_notes": "deterministic mixed delivery fixture",
            "generation_method": "built-in-imagegen",
            "categories": [
                {
                    "category": "Icon_Item",
                    "transparency_mode": "chroma-key",
                    "canvas": [256, 128],
                    "grid": [2, 1],
                    "target_size": [96, 96],
                    "outer_margin": 12,
                    "gutter": 12,
                    "safe_padding": 8,
                    "assets": ["HealthPotion", "ManaPotion"],
                },
                {
                    "category": "Icon_Effect",
                    "transparency_mode": "model-matte-derived",
                    "canvas": [256, 128],
                    "grid": [2, 1],
                    "target_size": [96, 96],
                    "outer_margin": 12,
                    "gutter": 12,
                    "safe_padding": 8,
                    "assets": ["Smoke", "SoftGlow"],
                },
            ],
        }

    def write_request(self, root: Path) -> Path:
        path = root / "batch-request.json"
        path.write_text(json.dumps(self.request()), encoding="utf-8")
        return path

    def jobs(self, run_dir: Path) -> dict[str, dict]:
        payload = json.loads((run_dir / "jobs.json").read_text(encoding="utf-8"))
        return {str(job["category"]): job for job in payload["jobs"]}

    def layout(self, run_dir: Path, job: dict) -> dict:
        return json.loads((run_dir / job["layout_json"]).read_text(encoding="utf-8"))

    def write_chroma_sheet(self, run_dir: Path) -> None:
        job = self.jobs(run_dir)["Icon_Item"]
        layout = self.layout(run_dir, job)
        array = np.zeros((128, 256, 3), dtype=np.uint8)
        array[:, :] = (0, 255, 0)
        colors = ((210, 45, 55), (45, 90, 220))
        for index, slot in enumerate(layout["slots"][:2]):
            safe = slot["safe_box"]
            left, top = safe["left"] + 8, safe["top"] + 8
            right, bottom = safe["right"] - 8, safe["bottom"] - 8
            array[top:bottom, left:right] = colors[index]
        Image.fromarray(array, mode="RGB").save(run_dir / job["generated_output"])

    def write_matte_sheet(self, run_dir: Path, color_bias: int = 0) -> None:
        job = self.jobs(run_dir)["Icon_Effect"]
        layout = self.layout(run_dir, job)
        color = np.zeros((128, 256, 3), dtype=np.uint8)
        matte = np.zeros((128, 256, 3), dtype=np.uint8)
        yy, xx = np.mgrid[0:128, 0:256]
        colors = ((90, 150, 230), (255, 205, 70))
        for index, slot in enumerate(layout["slots"][:2]):
            safe = slot["safe_box"]
            cx = (safe["left"] + safe["right"]) / 2
            cy = (safe["top"] + safe["bottom"]) / 2
            radius = min(safe["right"] - safe["left"], safe["bottom"] - safe["top"]) * 0.36
            distance = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
            alpha = np.clip((1.0 - distance / radius) * 240, 0, 240).astype(np.uint8)
            visible = alpha > 0
            for channel, value in enumerate(colors[index]):
                color[:, :, channel][visible] = value
            matte[:, :, 0] = np.maximum(matte[:, :, 0], alpha)
            matte[:, :, 1] = np.maximum(matte[:, :, 1], alpha)
            matte[:, :, 2] = np.maximum(matte[:, :, 2], np.clip(alpha.astype(int) + color_bias, 0, 255))
        Image.fromarray(color, mode="RGB").save(run_dir / job["generated_output"])
        Image.fromarray(matte, mode="RGB").save(run_dir / job["alpha_matte_output"])

    def test_prepares_waits_resumes_and_reuses_complete_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir = root / "run"
            request_path = self.write_request(root)

            waiting = ORCHESTRATOR.orchestrate(run_dir, request_path=request_path)
            self.assertTrue(waiting["ok"])
            self.assertEqual(waiting["status"], "awaiting-generation")
            self.assertEqual(waiting["generation"]["job_count"], 2)
            self.assertEqual(waiting["generation"]["missing_input_count"], 3)
            self.assertEqual(waiting["generation"]["policy"]["max_concurrent_image_jobs"], 3)
            self.assertEqual(waiting["generation"]["next_task"]["path"], "generated/current/icon-item-sheet-01.png")
            self.assertEqual(
                [task["path"] for task in waiting["generation"]["next_tasks"]],
                ["generated/current/icon-item-sheet-01.png", "generated/current/icon-effect-sheet-01.png"],
            )
            self.assertTrue((run_dir / "qa" / "delivery-summary.json").is_file())
            self.assertTrue((run_dir / "qa" / "delivery-summary.md").is_file())
            self.assertTrue((run_dir / "qa" / "pipeline-state.json").is_file())
            queue = json.loads((run_dir / "qa" / "generation-queue.json").read_text(encoding="utf-8"))
            self.assertEqual([task["status"] for task in queue["tasks"]], ["active", "active", "blocked"])

            self.write_chroma_sheet(run_dir)
            partial = ORCHESTRATOR.orchestrate(run_dir)
            self.assertEqual(partial["status"], "awaiting-generation")
            self.assertEqual(partial["generation"]["ready_job_count"], 1)
            self.assertEqual(partial["generation"]["missing_input_count"], 2)
            self.assertEqual(partial["generation"]["next_task"]["path"], "generated/current/icon-effect-sheet-01.png")

            self.write_matte_sheet(run_dir)
            complete = ORCHESTRATOR.orchestrate(run_dir)
            self.assertTrue(complete["ok"], complete)
            self.assertEqual(complete["status"], "complete")
            self.assertEqual(complete["results"]["exported"], 4)
            self.assertEqual(complete["results"]["pass"], 4)
            self.assertEqual(complete["results"]["fail"], 0)
            for path in ("final/manifest.json", "qa/contact-sheet.png", "qa/qa-report.json"):
                self.assertTrue((run_dir / path).is_file(), path)

            reused = ORCHESTRATOR.orchestrate(run_dir)
            self.assertTrue(reused["ok"])
            self.assertTrue(reused["reused_existing_delivery"])
            self.assertEqual(reused["status"], "complete")

    def test_multi_screen_unity_delivery_runs_after_adaptive_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir = root / "run"
            request = self.request()
            shared_asset = "06_Icon_Item_HealthPotion_Default_001"
            request["unity_delivery"] = {
                "enabled": True,
                "layout_confirmed": True,
                "unity_project": str(root / "UnityProject"),
                "unity_editor": str(root / "Unity.exe"),
                "layout": {
                    "schema_version": 1,
                    "screens": [
                        {
                            "id": "BagScreen",
                            "reference_size": [1920, 1080],
                            "elements": [
                                {"id": "SharedPotion", "kind": "Image", "asset_id": shared_asset, "size": [96, 96]}
                            ],
                        },
                        {
                            "id": "ShopScreen",
                            "reference_size": [1600, 900],
                            "elements": [
                                {"id": "SharedPotion", "kind": "Image", "asset_id": shared_asset, "size": [72, 72]}
                            ],
                        },
                    ],
                },
            }
            request_path = root / "batch-request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")

            waiting = ORCHESTRATOR.orchestrate(run_dir, request_path=request_path)
            self.assertEqual(waiting["status"], "awaiting-generation")
            self.assertTrue((run_dir / "unity" / "unity-layout.json").is_file())
            self.write_chroma_sheet(run_dir)
            ORCHESTRATOR.orchestrate(run_dir)
            self.write_matte_sheet(run_dir)

            def fake_unity_export(run_path, *_args):
                unity_dir = run_path / "unity"
                (unity_dir / "previews").mkdir(parents=True, exist_ok=True)
                report = {
                    "ok": True,
                    "screen_prefab_count": 2,
                    "preview_scene_count": 2,
                    "preview_image_count": 2,
                }
                (unity_dir / "unity-import-report.json").write_text(json.dumps(report), encoding="utf-8")
                for screen_id in ("BagScreen", "ShopScreen"):
                    (unity_dir / "previews" / f"{screen_id}.png").write_bytes(b"preview")
                return {"ok": True, "status": "complete", "results": report}

            with mock.patch.object(ORCHESTRATOR, "export_unity_ui", side_effect=fake_unity_export) as exporter:
                complete = ORCHESTRATOR.orchestrate(run_dir)
                self.assertTrue(complete["ok"], complete)
                self.assertEqual(complete["status"], "complete")
                self.assertEqual(complete["unity"]["screen_count"], 2)
                self.assertEqual(complete["unity"]["screens"], ["BagScreen", "ShopScreen"])
                exporter.assert_called_once()

                reused = ORCHESTRATOR.orchestrate(run_dir)
                self.assertTrue(reused["reused_existing_delivery"])
                exporter.assert_called_once()

    def test_accepts_adaptive_parallel_three_and_rejects_invalid_limits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            request = self.request()
            request["generation_policy"] = {
                "mode": "adaptive-parallel",
                "max_concurrent_image_jobs": 3,
            }
            request_path = root / "batch-request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            waiting = ORCHESTRATOR.orchestrate(root / "run", request_path=request_path)
            self.assertEqual(waiting["generation"]["runtime"]["effective_concurrency"], 3)

            invalid = self.request()
            invalid["generation_policy"] = {
                "mode": "adaptive-parallel",
                "max_concurrent_image_jobs": 4,
            }
            invalid_path = root / "invalid-request.json"
            invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "between 1 and 3"):
                ORCHESTRATOR.orchestrate(root / "invalid-run", request_path=invalid_path)

    def test_rejects_unity_layout_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory).resolve()
            with self.assertRaisesRegex(ValueError, "must stay inside the run directory"):
                ORCHESTRATOR.resolve_run_relative(run_dir, "../outside-layout.json", "unity_delivery.layout")

    def test_quick_source_gate_blocks_runner_and_uses_global_extra_call_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir = root / "run"
            request_path = self.write_request(root)
            ORCHESTRATOR.orchestrate(run_dir, request_path=request_path)
            self.write_chroma_sheet(run_dir)
            item_job = self.jobs(run_dir)["Icon_Item"]
            source_path = run_dir / item_job["generated_output"]
            image = np.asarray(Image.open(source_path).convert("RGB")).copy()
            image[0, 0] = (220, 20, 20)
            Image.fromarray(image, mode="RGB").save(source_path)

            with mock.patch.object(ORCHESTRATOR, "run_pipeline") as runner:
                blocked = ORCHESTRATOR.orchestrate(run_dir)

            runner.assert_not_called()
            self.assertTrue(blocked["ok"])
            self.assertEqual(blocked["status"], "awaiting-regeneration")
            self.assertEqual(blocked["retry"]["items"][0]["primary_issue"]["code"], "source-edge-contact")
            self.assertEqual(blocked["generation"]["budget"]["call_budget_range"], [3, 5])
            self.assertEqual(blocked["generation"]["budget"]["extra_calls_committed"], 1)
            self.assertTrue((run_dir / "qa" / "source-gate-summary.json").is_file())
            queue = json.loads((run_dir / "qa" / "generation-queue.json").read_text(encoding="utf-8"))
            self.assertEqual(queue["active_task"]["path"], item_job["generated_output"])
            self.assertIn("retry-02.md", queue["active_task"]["prompt_file"])

    def test_quick_source_gate_scales_layout_boxes_for_same_aspect_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir = root / "run"
            request_path = self.write_request(root)
            ORCHESTRATOR.orchestrate(run_dir, request_path=request_path)
            item_job = self.jobs(run_dir)["Icon_Item"]
            layout = self.layout(run_dir, item_job)
            array = np.zeros((64, 128, 3), dtype=np.uint8)
            array[:, :] = (0, 255, 0)
            for slot in layout["slots"][:2]:
                box = slot["safe_box"]
                left = int(round(box["left"] * 0.5))
                right = int(round(box["right"] * 0.5))
                top = int(round(box["top"] * 0.5))
                bottom = int(round(box["bottom"] * 0.5))
                array[top:bottom, left:right] = (220, 20, 20)
            source_path = run_dir / item_job["generated_output"]
            source_path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(array, mode="RGB").save(source_path)

            report = ORCHESTRATOR.validate_source_sheet(item_job, run_dir)

            self.assertTrue(report["ok"])
            self.assertEqual(report["checks"]["actual_size"], [128, 64])
            self.assertEqual(report["checks"]["occupied_slots"], [1, 2])
            self.assertEqual(report["checks"]["slot_detection_scale"], [0.5, 0.5])

    def test_quick_source_gate_cache_changes_when_request_contract_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir = root / "run"
            request_path = self.write_request(root)
            ORCHESTRATOR.orchestrate(run_dir, request_path=request_path)
            self.write_chroma_sheet(run_dir)
            item_job = self.jobs(run_dir)["Icon_Item"]

            first = ORCHESTRATOR.validate_source_sheet(item_job, run_dir)
            request_file = run_dir / item_job["request_file"]
            request = json.loads(request_file.read_text(encoding="utf-8"))
            request["cache_contract_probe"] = "changed"
            request_file.write_text(json.dumps(request), encoding="utf-8")
            second = ORCHESTRATOR.validate_source_sheet(item_job, run_dir)

            self.assertNotEqual(first["contract_fingerprint"], second["contract_fingerprint"])
            self.assertEqual(second["schema_version"], 3)

    def test_quick_source_gate_rejects_panel_decoration_in_stretch_band(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory)
            for relative in ("generated/current", "requests", "references/layout-guides"):
                (run_dir / relative).mkdir(parents=True, exist_ok=True)
            job = {
                "id": "panel-sheet-01",
                "category": "Panel",
                "expected_count": 1,
                "transparency_mode": "chroma-key",
                "generated_output": "generated/current/panel-sheet-01.png",
                "request_file": "requests/panel-sheet-01.json",
                "layout_json": "references/layout-guides/panel-sheet-01.json",
            }
            (run_dir / job["request_file"]).write_text(
                json.dumps({"chroma_key": "#00FF00"}),
                encoding="utf-8",
            )
            (run_dir / job["layout_json"]).write_text(
                json.dumps(
                    {
                        "layout": {"width": 200, "height": 200},
                        "slots": [{"index": 1, "slot": {"left": 0, "top": 0, "right": 200, "bottom": 200}}],
                    }
                ),
                encoding="utf-8",
            )
            image = Image.new("RGB", (200, 200), (0, 255, 0))
            draw = ImageDraw.Draw(image)
            draw.rectangle((20, 20, 180, 180), outline=(180, 100, 30), width=18)
            draw.rectangle((80, 5, 120, 50), fill=(20, 40, 220))
            image.save(run_dir / job["generated_output"])

            report = ORCHESTRATOR.validate_source_sheet(job, run_dir)

            self.assertFalse(report["ok"])
            self.assertIn("panel-stretch-band-decoration", {issue["code"] for issue in report["issues"]})

    def test_runtime_preflight_rejects_backups_inside_generated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir = root / "run"
            request_path = self.write_request(root)
            ORCHESTRATOR.orchestrate(run_dir, request_path=request_path)
            (run_dir / "generated" / "old-backup.png").write_bytes(b"backup")

            blocked = ORCHESTRATOR.orchestrate(run_dir)

            self.assertFalse(blocked["ok"])
            self.assertEqual(blocked["status"], "configuration-invalid")
            self.assertEqual(
                blocked["preflight"]["issues"][0]["code"],
                "generated-directory-contaminated",
            )

    def test_adaptive_queue_uses_three_slots_but_only_two_high_risk_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory)
            jobs = []
            for sequence, category in enumerate(("Panel", "Button", "Icon_Status", "Icon_Item"), start=1):
                jobs.append(
                    {
                        "id": f"job-{sequence}",
                        "category": category,
                        "expected_count": 1,
                        "generation_sequence": sequence,
                        "transparency_mode": "chroma-key",
                        "generated_output": f"generated/job-{sequence}.png",
                        "prompt_file": f"prompts/job-{sequence}.md",
                    }
                )
            policy = ORCHESTRATOR.normalized_generation_policy({})
            runtime = ORCHESTRATOR.generation_runtime_state(run_dir, policy)

            queue = ORCHESTRATOR.build_generation_queue(jobs, run_dir, policy, runtime)

            self.assertEqual(queue["effective_concurrency"], 3)
            self.assertEqual(queue["wave_kind"], "risk-production")
            self.assertEqual(
                [task["category"] for task in queue["active_tasks"]],
                ["Panel", "Button"],
            )

    def test_matte_inputs_and_retries_are_exclusive_serial_waves(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory)
            (run_dir / "generated").mkdir(parents=True)
            jobs = []
            for sequence in (1, 2):
                source = run_dir / "generated" / f"effect-{sequence}.png"
                source.write_bytes(f"source-{sequence}".encode())
                jobs.append(
                    {
                        "id": f"effect-{sequence}",
                        "category": "Icon_Effect",
                        "expected_count": 1,
                        "generation_sequence": sequence,
                        "transparency_mode": "model-matte-derived",
                        "generated_output": f"generated/effect-{sequence}.png",
                        "alpha_matte_output": f"generated/effect-{sequence}-alpha-matte.png",
                        "prompt_file": f"prompts/effect-{sequence}.md",
                        "alpha_matte_prompt_file": f"prompts/effect-{sequence}-matte.md",
                    }
                )
            policy = ORCHESTRATOR.normalized_generation_policy({})
            runtime = ORCHESTRATOR.generation_runtime_state(run_dir, policy)
            matte_queue = ORCHESTRATOR.build_generation_queue(jobs, run_dir, policy, runtime)
            self.assertEqual(matte_queue["wave_kind"], "dependent")
            self.assertEqual(len(matte_queue["active_tasks"]), 1)
            self.assertEqual(matte_queue["active_tasks"][0]["kind"], "alpha-matte")

            first = jobs[0]
            first["retry"] = {
                "target_paths": [first["generated_output"]],
                "awaiting_hashes": {
                    first["generated_output"]: ORCHESTRATOR.file_sha256(
                        run_dir / first["generated_output"]
                    )
                },
                "prompt_file": "prompts/effect-1-retry.md",
            }
            retry_queue = ORCHESTRATOR.build_generation_queue(jobs, run_dir, policy, runtime)
            self.assertEqual(retry_queue["wave_kind"], "retry")
            self.assertEqual(len(retry_queue["active_tasks"]), 1)
            self.assertTrue(retry_queue["active_tasks"][0]["is_retry"])

    def test_generation_failures_degrade_concurrency_three_to_two_to_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory)
            policy = ORCHESTRATOR.normalized_generation_policy({})
            initial = ORCHESTRATOR.generation_runtime_state(run_dir, policy)
            after_limit = ORCHESTRATOR.generation_runtime_state(run_dir, policy, "rate-limit")
            after_timeout = ORCHESTRATOR.generation_runtime_state(run_dir, policy, "timeout")
            after_disconnect = ORCHESTRATOR.generation_runtime_state(run_dir, policy, "disconnect")

            self.assertEqual(initial["effective_concurrency"], 3)
            self.assertEqual(after_limit["effective_concurrency"], 2)
            self.assertEqual(after_timeout["effective_concurrency"], 1)
            self.assertEqual(after_disconnect["effective_concurrency"], 1)

    def test_duplicate_consecutive_generation_failure_is_recorded_without_double_degradation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory)
            policy = ORCHESTRATOR.normalized_generation_policy({})
            first = ORCHESTRATOR.generation_runtime_state(run_dir, policy, "timeout")
            duplicate = ORCHESTRATOR.generation_runtime_state(run_dir, policy, "timeout")

            self.assertEqual(first["effective_concurrency"], 2)
            self.assertEqual(duplicate["effective_concurrency"], 2)
            self.assertTrue(duplicate["degradation_events"][-1]["deduplicated"])

    def test_zero_extra_call_budget_turns_quick_gate_failure_into_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir = root / "run"
            request = self.request()
            request["generation_budget"] = {"max_extra_calls": 0, "estimated_minutes_per_call": [5, 8]}
            request_path = root / "batch-request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            ORCHESTRATOR.orchestrate(run_dir, request_path=request_path)
            self.write_chroma_sheet(run_dir)
            self.write_matte_sheet(run_dir)
            item_job = self.jobs(run_dir)["Icon_Item"]
            source_path = run_dir / item_job["generated_output"]
            image = np.asarray(Image.open(source_path).convert("RGB")).copy()
            image[0, 0] = (220, 20, 20)
            Image.fromarray(image, mode="RGB").save(source_path)

            blocked = ORCHESTRATOR.orchestrate(run_dir)

            self.assertFalse(blocked["ok"])
            self.assertEqual(blocked["status"], "failed")
            self.assertEqual(blocked["retry"]["budget_exhausted_jobs"], ["icon-item-sheet-01"])

    def test_failed_matte_preflight_can_resume_after_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir = root / "run"
            request_path = self.write_request(root)
            ORCHESTRATOR.orchestrate(run_dir, request_path=request_path)
            self.write_chroma_sheet(run_dir)
            self.write_matte_sheet(run_dir, color_bias=120)

            failed = ORCHESTRATOR.orchestrate(run_dir)
            self.assertTrue(failed["ok"])
            self.assertEqual(failed["status"], "awaiting-regeneration")
            self.assertFalse((run_dir / "final" / "manifest.json").exists())
            self.assertIn("Icon_Effect".lower().replace("_", "-"), " ".join(failed["results"]["manual_action_required"]))
            self.assertEqual(len(failed["retry"]["items"]), 1)
            retry_item = failed["retry"]["items"][0]
            self.assertEqual(retry_item["job_id"], "icon-effect-sheet-01")
            self.assertEqual(retry_item["primary_issue"]["retry_target"], "alpha-matte")
            self.assertTrue((run_dir / retry_item["prompt_file"]).is_file())
            self.assertTrue((run_dir / "qa" / "regeneration-plan.json").is_file())

            unchanged = ORCHESTRATOR.orchestrate(run_dir)
            self.assertTrue(unchanged["ok"])
            self.assertEqual(unchanged["status"], "awaiting-regeneration")
            jobs = self.jobs(run_dir)
            self.assertEqual(len(jobs["Icon_Effect"]["candidate_history"]), 1)

            self.write_matte_sheet(run_dir)
            recovered = ORCHESTRATOR.orchestrate(run_dir)
            self.assertTrue(recovered["ok"], recovered)
            self.assertEqual(recovered["status"], "complete")
            self.assertGreaterEqual(recovered["results"]["quality_score"], 90)
            self.assertEqual(recovered["results"]["hard_blocker_count"], 0)
            self.assertFalse((run_dir / "qa" / "regeneration-plan.json").exists())

    def test_retry_budget_exhaustion_remains_a_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir = root / "run"
            request = self.request()
            request["retry_policy"] = {"max_attempts": 1}
            request_path = root / "batch-request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            ORCHESTRATOR.orchestrate(run_dir, request_path=request_path)
            self.write_chroma_sheet(run_dir)
            self.write_matte_sheet(run_dir, color_bias=120)

            failed = ORCHESTRATOR.orchestrate(run_dir)
            self.assertFalse(failed["ok"])
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["retry"]["items"], [])
            self.assertEqual(failed["retry"]["exhausted_jobs"], ["icon-effect-sheet-01"])

    def test_unprepared_run_requires_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(FileNotFoundError, "requires --request"):
                ORCHESTRATOR.orchestrate(Path(temporary_directory) / "run")

    def test_native_alpha_job_waits_for_provenance_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory)
            source = run_dir / "generated" / "effect.png"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"placeholder")
            job = {
                "id": "effect",
                "category": "Icon_Effect",
                "expected_count": 1,
                "transparency_mode": "native-alpha-required",
                "generated_output": "generated/effect.png",
                "prompt_file": "prompts/effect.md",
                "provenance_file": "generated/effect.provenance.json",
            }
            inputs = ORCHESTRATOR.required_inputs(job, run_dir)
            self.assertEqual([item["kind"] for item in inputs], [
                "production-sheet", "native-alpha-provenance"
            ])
            self.assertTrue(inputs[0]["exists"])
            self.assertFalse(inputs[1]["exists"])

    def test_multi_input_retry_waits_until_every_planned_target_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory)
            generated = run_dir / "generated" / "effect.png"
            matte = run_dir / "generated" / "effect-alpha-matte.png"
            generated.parent.mkdir(parents=True)
            generated.write_bytes(b"color-v1")
            matte.write_bytes(b"matte-v1")
            job = {
                "id": "effect",
                "category": "Icon_Effect",
                "expected_count": 1,
                "transparency_mode": "model-matte-derived",
                "generated_output": "generated/effect.png",
                "alpha_matte_output": "generated/effect-alpha-matte.png",
                "prompt_file": "prompts/effect.md",
                "alpha_matte_prompt_file": "prompts/effect-alpha-matte.md",
            }
            targets = [job["generated_output"], job["alpha_matte_output"]]
            job["retry"] = {
                "target_paths": targets,
                "awaiting_fingerprint": ORCHESTRATOR.candidate_fingerprint(job, run_dir),
                "awaiting_hashes": {
                    path: ORCHESTRATOR.file_sha256(run_dir / path) for path in targets
                },
            }

            generated.write_bytes(b"color-v2")
            partial = ORCHESTRATOR.generation_state([job], run_dir)
            self.assertFalse(partial["jobs"][0]["ready"])
            self.assertEqual(partial["jobs"][0]["pending_replacements"], [job["alpha_matte_output"]])

            matte.write_bytes(b"matte-v2")
            ready = ORCHESTRATOR.generation_state([job], run_dir)
            self.assertTrue(ready["jobs"][0]["ready"])
            self.assertTrue(ready["jobs"][0]["retry_candidate_ready"])

    def test_asset_validation_blocker_retries_even_when_extraction_job_was_ok(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory)
            (run_dir / "generated").mkdir(parents=True)
            (run_dir / "prompts").mkdir(parents=True)
            (run_dir / "qa").mkdir(parents=True)
            (run_dir / "generated" / "item.png").write_bytes(b"candidate")
            (run_dir / "prompts" / "item.md").write_text("original prompt", encoding="utf-8")
            job = {
                "id": "item",
                "category": "Icon_Item",
                "expected_count": 1,
                "transparency_mode": "chroma-key",
                "generated_output": "generated/item.png",
                "prompt_file": "prompts/item.md",
                "input_images": [],
            }
            qa_report = {
                "jobs": [{"id": "item", "ok": True}],
                "issues": [
                    {
                        "severity": "fail",
                        "code": "visible-chroma-spill",
                        "job_id": "item",
                        "asset_id": "06_Icon_Item_Test_Default_001",
                    }
                ],
                "quality": {
                    "jobs": [
                        {"id": "item", "score": 68, "status": "blocked", "hard_blocker_count": 1}
                    ]
                },
            }
            jobs_payload = {"schema_version": 2, "jobs": [job]}
            plan = ORCHESTRATOR.write_regeneration_plan(
                run_dir,
                {"retry_policy": {"max_attempts": 3}},
                jobs_payload,
                qa_report,
            )
            self.assertEqual(plan["status"], "awaiting-regeneration")
            self.assertEqual(plan["items"][0]["primary_issue"]["code"], "visible-chroma-spill")
            updated = json.loads((run_dir / "jobs.json").read_text(encoding="utf-8"))["jobs"][0]
            self.assertFalse(updated["candidate_history"][0]["ok"])


if __name__ == "__main__":
    unittest.main()
