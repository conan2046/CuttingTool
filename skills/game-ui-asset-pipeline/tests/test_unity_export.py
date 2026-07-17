from __future__ import annotations

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


NINE_SLICE = load_module("infer_nine_slice")
UNITY_EXPORT = load_module("prepare_unity_export")
UNITY_ROLLBACK = load_module("rollback_unity_export")


def frame_image(size: int = 128, border: int = 14) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, size - 1, size - 1), fill=(212, 170, 64, 255))
    draw.rectangle((border, border, size - border - 1, size - border - 1), fill=(30, 40, 55, 220))
    return image


class UnityExportTest(unittest.TestCase):
    def test_infers_high_confidence_frame_border(self) -> None:
        result = NINE_SLICE.infer_nine_slice(frame_image())
        self.assertTrue(result["apply"], result)
        self.assertGreaterEqual(result["confidence"], 0.65)
        for value in result["border"]:
            self.assertGreaterEqual(value, 4)
            self.assertLess(value, 58)

    def test_uniform_image_requires_manual_override(self) -> None:
        result = NINE_SLICE.infer_nine_slice(Image.new("RGBA", (128, 128), (255, 255, 255, 255)))
        self.assertFalse(result["apply"])
        self.assertIn("nine-slice-low-confidence-manual-override-required", result["issues"])

    def test_prepares_unity_package_sprites_layout_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir = root / "run"
            unity_project = root / "UnityProject"
            (unity_project / "Assets").mkdir(parents=True)
            (unity_project / "Packages").mkdir()
            (unity_project / "ProjectSettings").mkdir()
            (unity_project / "ProjectSettings" / "ProjectVersion.txt").write_text(
                "m_EditorVersion: 2022.3.62f3c1\n", encoding="utf-8"
            )
            final = run_dir / "final" / "Panel"
            final.mkdir(parents=True)
            panel = final / "01_Panel_Main_Default_001.png"
            frame_image().save(panel)
            manifest = {
                "schema_version": 1,
                "project_id": "commercial-ui",
                "assets": [
                    {
                        "id": "01_Panel_Main_Default_001",
                        "category": "Panel",
                        "semantic_name": "Main",
                        "state": "Default",
                        "output": "final/Panel/01_Panel_Main_Default_001.png",
                        "pivot": [0.5, 0.5],
                        "qa": "pass",
                    }
                ],
            }
            (run_dir / "final" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (run_dir / "qa").mkdir()
            (run_dir / "qa" / "qa-report.json").write_text(
                json.dumps({"schema_version": 2, "ok": True, "fail_count": 0}), encoding="utf-8"
            )
            layout = {
                "schema_version": 1,
                "screens": [
                    {
                        "id": "main-screen",
                        "name": "MainScreen",
                        "reference_size": [1920, 1080],
                        "elements": [
                            {
                                "id": "MainPanel",
                                "asset_id": "01_Panel_Main_Default_001",
                                "kind": "Image",
                                "size": [1200, 800],
                            }
                        ],
                    }
                ],
            }
            layout_path = root / "unity-layout.json"
            layout_path.write_text(json.dumps(layout), encoding="utf-8")

            result = UNITY_EXPORT.prepare_unity_export(
                run_dir,
                unity_project,
                SKILL_DIR / "assets" / "unity-package",
                layout_path,
            )

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["sprite_count"], 1)
            self.assertEqual(result["screen_count"], 1)
            self.assertTrue((unity_project / "Packages" / "com.hongda.game-ui-asset-pipeline" / "package.json").is_file())
            plan = json.loads((run_dir / "unity" / "unity-import-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["sprites"][0]["border_origin"], "auto-inferred")
            self.assertEqual(plan["screens"][0]["elements"][0]["id"], "MainPanel")
            rollback = json.loads((run_dir / "unity" / "unity-rollback.json").read_text(encoding="utf-8"))
            self.assertEqual(rollback["generated_root"], "Assets/_Generated/GameUI/commercial-ui")
            rollback_result = UNITY_ROLLBACK.rollback(run_dir / "unity" / "unity-rollback.json")
            self.assertTrue(rollback_result["ok"])
            self.assertFalse((unity_project / "Assets" / "_Generated" / "GameUI" / "commercial-ui").exists())
            self.assertTrue((unity_project / "Packages" / "com.hongda.game-ui-asset-pipeline").is_dir())

    def test_rejects_layout_path_escape_and_unknown_assets(self) -> None:
        with self.assertRaisesRegex(ValueError, "Assets"):
            UNITY_EXPORT.validate_asset_path("../Outside")
        layout = {
            "schema_version": 1,
            "screens": [
                {
                    "id": "bad",
                    "reference_size": [100, 100],
                    "elements": [{"id": "Child", "parent_id": "Missing", "kind": "Image"}],
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "parent_id must reference an earlier element"):
            UNITY_EXPORT.normalize_layout(layout)

    def test_rejects_parent_declared_after_child(self) -> None:
        layout = {
            "schema_version": 1,
            "screens": [
                {
                    "id": "bad-order",
                    "reference_size": [100, 100],
                    "elements": [
                        {"id": "Child", "parent_id": "Parent", "kind": "Image"},
                        {"id": "Parent", "kind": "Image"},
                    ],
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "earlier element"):
            UNITY_EXPORT.normalize_layout(layout)

    def test_rejects_nine_slice_override_without_center(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir = root / "run"
            project = root / "UnityProject"
            (project / "Assets").mkdir(parents=True)
            (project / "Packages").mkdir()
            (project / "ProjectSettings").mkdir()
            (project / "ProjectSettings" / "ProjectVersion.txt").write_text(
                "m_EditorVersion: 2022.3.62f3c1\n", encoding="utf-8"
            )
            asset = run_dir / "final" / "Panel" / "panel.png"
            asset.parent.mkdir(parents=True)
            frame_image().save(asset)
            (run_dir / "final" / "manifest.json").write_text(
                json.dumps(
                    {
                        "project_id": "bad-border",
                        "assets": [{"id": "Panel", "category": "Panel", "output": "final/Panel/panel.png"}],
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "qa").mkdir()
            (run_dir / "qa" / "qa-report.json").write_text(
                json.dumps({"ok": True, "fail_count": 0}), encoding="utf-8"
            )
            layout_path = root / "layout.json"
            layout_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "nine_slice_overrides": {"Panel": [64, 0, 64, 0]},
                        "screens": [
                            {
                                "id": "Screen",
                                "reference_size": [100, 100],
                                "elements": [{"id": "Panel", "asset_id": "Panel", "kind": "Image"}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "no stretchable center"):
                UNITY_EXPORT.prepare_unity_export(
                    run_dir, project, SKILL_DIR / "assets" / "unity-package", layout_path
                )

    def test_unity_runner_deletes_stale_report_before_launch(self) -> None:
        source = (SCRIPTS_DIR / "export_unity_ui.py").read_text(encoding="utf-8")
        self.assertIn("report_path.unlink(missing_ok=True)", source)
        importer = (SKILL_DIR / "assets" / "unity-package" / "Editor" / "GameUIBatchImporter.cs").read_text(
            encoding="utf-8"
        )
        self.assertIn('spritePlan.category, "Button"', importer)

    def test_rejects_missing_or_failed_formal_qa(self) -> None:
        source = (SCRIPTS_DIR / "prepare_unity_export.py").read_text(encoding="utf-8")
        self.assertIn("formal QA report not found", source)
        self.assertIn("formal QA has unresolved failures", source)


if __name__ == "__main__":
    unittest.main()
