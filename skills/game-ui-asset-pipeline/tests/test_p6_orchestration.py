import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


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
            self.assertTrue((run_dir / "qa" / "delivery-summary.json").is_file())
            self.assertTrue((run_dir / "qa" / "delivery-summary.md").is_file())

            self.write_chroma_sheet(run_dir)
            partial = ORCHESTRATOR.orchestrate(run_dir)
            self.assertEqual(partial["status"], "awaiting-generation")
            self.assertEqual(partial["generation"]["ready_job_count"], 1)
            self.assertEqual(partial["generation"]["missing_input_count"], 2)

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
