import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

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


PREPARE = load_module("prepare_ui_batch")
RUNNER = load_module("run_ui_pipeline")


class BatchPipelineTest(unittest.TestCase):
    def request_spec(self) -> dict:
        return {
            "project_id": "Multi Category Test",
            "style_notes": "synthetic deterministic test",
            "categories": [
                {
                    "category": "Icon_Item",
                    "canvas": [256, 256],
                    "grid": [2, 2],
                    "target_size": [64, 64],
                    "outer_margin": 16,
                    "gutter": 8,
                    "safe_padding": 12,
                    "fragment_policy": {
                        "detached_action": "allow-small",
                        "small_detached_max_pixels": 20,
                        "small_detached_max_anchor_ratio": 0.01,
                    },
                    "assets": [f"Item{index}" for index in range(1, 6)],
                },
                {
                    "category": "Button",
                    "canvas": [768, 128],
                    "grid": [3, 1],
                    "target_size": [96, 48],
                    "outer_margin": 8,
                    "gutter": 8,
                    "safe_padding": 8,
                    "assets": [
                        {"semantic_name": "Confirm", "state": "Normal"},
                        {"semantic_name": "Confirm", "state": "Pressed"},
                        {"semantic_name": "Confirm", "state": "Disabled"},
                    ],
                },
            ],
        }

    def create_generated_sheets(self, run_dir: Path) -> None:
        jobs = json.loads((run_dir / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        colors = ((190, 40, 30), (35, 80, 210), (220, 130, 20), (105, 45, 170))
        for job in jobs:
            request = json.loads((run_dir / job["request_file"]).read_text(encoding="utf-8"))
            layout = json.loads((run_dir / job["layout_json"]).read_text(encoding="utf-8"))
            if request["category"] == "Button":
                image = Image.new("RGBA", tuple(request["canvas"]), (0, 0, 0, 0))
            else:
                image = Image.new("RGB", tuple(request["canvas"]), request["chroma_key"])
            draw = ImageDraw.Draw(image)
            for index, asset in enumerate(request["assets"]):
                safe = layout["slots"][index]["safe_box"]
                inset = 4
                box = (safe["left"] + inset, safe["top"] + inset, safe["right"] - inset, safe["bottom"] - inset)
                if request["category"] == "Button":
                    draw.rounded_rectangle(box, radius=8, fill=colors[index % len(colors)])
                else:
                    draw.ellipse(box, fill=colors[index % len(colors)])
            image.save(run_dir / job["generated_output"])

    def test_splits_categories_and_runs_complete_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            PREPARE.prepare_batch(self.request_spec(), run_dir)
            jobs = json.loads((run_dir / "jobs.json").read_text(encoding="utf-8"))["jobs"]
            self.assertEqual([job["id"] for job in jobs], [
                "icon-item-sheet-01",
                "icon-item-sheet-02",
                "button-sheet-01",
            ])
            self.assertEqual([job["expected_count"] for job in jobs], [4, 1, 3])
            first_job_request = json.loads((run_dir / jobs[0]["request_file"]).read_text(encoding="utf-8"))
            self.assertEqual(first_job_request["fragment_policy"]["detached_action"], "allow-small")
            self.create_generated_sheets(run_dir)

            result = RUNNER.run_pipeline(run_dir)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["expected"], 8)
            manifest = json.loads((run_dir / "final" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["exported_count"], 8)
            self.assertEqual(manifest["fragment_policies"]["Icon_Item"]["detached_action"], "allow-small")
            item_entries = [entry for entry in manifest["assets"] if entry["category"] == "Icon_Item"]
            self.assertEqual([entry["category_index"] for entry in item_entries], [1, 2, 3, 4, 5])
            required = {"source_sheet", "source_index", "source_bbox", "output", "padding", "alignment", "pivot"}
            self.assertTrue(required.issubset(item_entries[0]))
            self.assertTrue((run_dir / item_entries[0]["output"]).is_file())
            qa = json.loads((run_dir / "qa" / "qa-report.json").read_text(encoding="utf-8"))
            summary = json.loads((run_dir / "qa" / "run-summary.json").read_text(encoding="utf-8"))
            self.assertTrue(qa["ok"], qa)
            self.assertEqual(len(qa["nine_slice_stretch_bands"]), 3)
            self.assertTrue(all(item["category"] == "Button" for item in qa["nine_slice_stretch_bands"]))
            self.assertEqual(summary["status"], "complete")
            self.assertTrue((run_dir / "qa" / "contact-sheet.png").is_file())
            button_background = json.loads(
                (run_dir / "qa" / "button-sheet-01-background.json").read_text(encoding="utf-8")
            )
            self.assertEqual(button_background["background_mode"], "existing-alpha")

            with self.assertRaises(FileExistsError):
                RUNNER.run_pipeline(run_dir)

    def test_runner_rejects_missing_generated_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            PREPARE.prepare_batch(self.request_spec(), run_dir)
            with self.assertRaises(FileNotFoundError):
                RUNNER.run_pipeline(run_dir)

    def test_runner_rejects_generated_canvas_aspect_ratio_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            PREPARE.prepare_batch(self.request_spec(), run_dir)
            self.create_generated_sheets(run_dir)
            jobs = json.loads((run_dir / "jobs.json").read_text(encoding="utf-8"))["jobs"]
            first_generated = run_dir / jobs[0]["generated_output"]
            with Image.open(first_generated) as image:
                image.resize((256, 128)).save(first_generated)

            with self.assertRaisesRegex(ValueError, "generated-canvas-aspect-ratio-mismatch"):
                RUNNER.run_pipeline(run_dir)

    def test_state_group_is_not_split_across_sheets(self) -> None:
        assets = [
            {"semantic_name": "Confirm", "state": "Normal"},
            {"semantic_name": "Secondary", "state": "Normal"},
            {"semantic_name": "Confirm", "state": "Pressed"},
            {"semantic_name": "Confirm", "state": "Disabled"},
        ]
        chunks = PREPARE.split_assets(assets, 3)
        self.assertEqual([[item["semantic_name"] for item in chunk] for chunk in chunks], [
            ["Confirm", "Confirm", "Confirm"],
            ["Secondary"],
        ])
        with self.assertRaises(ValueError):
            PREPARE.split_assets([{"semantic_name": "Oversized"}] * 4, 3)

    def test_panel_defaults_to_one_compact_asset_per_frame_style(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            PREPARE.prepare_batch(
                {
                    "project_id": "panel-reuse",
                    "categories": [
                        {
                            "category": "Panel",
                            "assets": [
                                {"semantic_name": "Main", "frame_style": "jade"},
                                {"semantic_name": "Dialog", "frame_style": "jade"},
                                {"semantic_name": "Dragon", "frame_style": "dragon"},
                            ],
                        }
                    ],
                },
                run_dir,
            )

            request = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
            panel = request["categories"][0]
            self.assertEqual(panel["canvas"], [1024, 1024])
            self.assertEqual(panel["grid"], [1, 1])
            self.assertEqual(panel["target_size"], [200, 200])
            self.assertEqual([asset["semantic_name"] for asset in panel["assets"]], ["Main", "Dragon"])
            self.assertEqual(panel["reuse_aliases"][0]["semantic_name"], "Dialog")
            jobs = json.loads((run_dir / "jobs.json").read_text(encoding="utf-8"))["jobs"]
            self.assertEqual([job["expected_count"] for job in jobs], [1, 1])

    def test_auto_chroma_uses_declared_palette_and_is_traceable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            PREPARE.prepare_batch(
                {
                    "project_id": "palette-aware",
                    "categories": [
                        {
                            "category": "Icon_Item",
                            "subject_colors": ["green", "purple"],
                            "assets": [{"semantic_name": "JadePurpleStone", "description": "绿色与紫色宝石"}],
                        }
                    ],
                },
                run_dir,
            )

            request = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
            category = request["categories"][0]
            self.assertEqual(category["chroma_key"], "#00FFFF")
            self.assertEqual(category["chroma_key_selection"]["declared_conflicts"], ["green", "magenta"])
            self.assertEqual(category["chroma_key_selection"]["mode"], "auto-declared-palette")
            self.assertTrue((run_dir / "qa" / "request-preflight.json").is_file())
            self.assertTrue((run_dir / "generated" / "current").is_dir())
            self.assertTrue((run_dir / "reused-staging").is_dir())
            self.assertTrue((run_dir / ".local" / "backups").is_dir())

    def test_explicit_chroma_conflict_fails_before_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(ValueError, "conflicts with declared green"):
                PREPARE.prepare_batch(
                    {
                        "project_id": "bad-palette",
                        "categories": [
                            {
                                "category": "Icon_Status",
                                "chroma_key": "#00FF00",
                                "subject_uses_green": True,
                                "assets": ["Poison"],
                            }
                        ],
                    },
                    Path(temporary_directory) / "run",
                )

    def test_unity_layout_schema_fails_during_request_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            unity_project = root / "UnityProject"
            unity_project.mkdir()
            editor = root / "Unity.exe"
            editor.write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "spacing must contain two numbers"):
                PREPARE.prepare_batch(
                    {
                        "project_id": "invalid-layout",
                        "categories": [{"category": "Icon_Item", "assets": ["Potion"]}],
                        "unity_delivery": {
                            "enabled": True,
                            "layout_confirmed": True,
                            "unity_project": str(unity_project),
                            "unity_editor": str(editor),
                            "layout": {
                                "schema_version": 1,
                                "screens": [
                                    {
                                        "id": "Bag",
                                        "reference_size": [1920, 1080],
                                        "elements": [
                                            {
                                                "id": "Row",
                                                "kind": "HorizontalLayoutGroup",
                                                "spacing": 12,
                                                "size": [400, 80],
                                            }
                                        ],
                                    }
                                ],
                            },
                        },
                    },
                    root / "run",
                )


if __name__ == "__main__":
    unittest.main()
