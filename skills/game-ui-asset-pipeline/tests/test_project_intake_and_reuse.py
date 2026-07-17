from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"


def load_module(name: str):
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


INTAKE = load_module("compile_ui_project_intake")
CATALOG = load_module("update_project_asset_catalog")


class ProjectIntakeAndReuseTest(unittest.TestCase):
    def analysis(self, canonical: Path) -> dict:
        return {
            "project_id": "xianxia-ui",
            "project_name": "修仙 UI",
            "canonical_reference": {
                "file": str(canonical),
                "role": "布局和风格主参考",
                "analysis": "青玉鎏金，正面平视",
            },
            "supporting_references": [],
            "screens": [
                {
                    "id": "bag",
                    "name": "背包",
                    "target_size": [1920, 1080],
                    "layout_confirmed": True,
                    "elements_match_canonical": True,
                    "assets": [
                        {"category": "Panel", "semantic_name": "MainBag"},
                        {"category": "Icon_General", "semantic_name": "Close"},
                    ],
                },
                {
                    "id": "shop",
                    "name": "商店",
                    "target_size": [1600, 900],
                    "layout_confirmed": True,
                    "elements_match_canonical": False,
                    "difference_notes": "商店使用双栏，但沿用主参考材质和控件造型。",
                    "assets": [
                        {"category": "Icon_General", "semantic_name": "Close"},
                        {"category": "Panel", "semantic_name": "ShopList"},
                    ],
                },
            ],
        }

    def test_compiles_notes_inventory_and_skips_later_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory)
            canonical = project_dir / "references" / "canonical-style.png"
            canonical.parent.mkdir(parents=True)
            canonical.write_bytes(b"fixture")
            notes = canonical.parent / "reference-notes.md"
            notes.write_text("用户保留说明\n", encoding="utf-8")

            result = INTAKE.compile_intake(project_dir, self.analysis(canonical))

            self.assertEqual(result["generate_count"], 3)
            self.assertEqual(result["reuse_count"], 1)
            notes_text = notes.read_text(encoding="utf-8")
            self.assertIn("用户保留说明", notes_text)
            self.assertIn("Codex 根据参考图和用户确认自动维护", notes_text)
            self.assertIn("1600×900", notes_text)
            inventory = json.loads((project_dir / "ui-resource-inventory.json").read_text(encoding="utf-8"))
            close_rows = [item for item in inventory["assets"] if item["semantic_name"] == "Close"]
            self.assertEqual([item["action"] for item in close_rows], ["generate", "reuse"])
            self.assertTrue(close_rows[1]["reuse_asset_id"].startswith("pending:"))
            request = json.loads((project_dir / "batch-request.json").read_text(encoding="utf-8"))
            generated = [asset for category in request["categories"] for asset in category["assets"]]
            self.assertEqual(len(generated), 3)

    def test_later_screen_reuses_project_catalog_ignoring_size(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory)
            canonical = project_dir / "references" / "canonical-style.png"
            canonical.parent.mkdir(parents=True)
            canonical.write_bytes(b"fixture")
            catalog = {
                "schema_version": 1,
                "assets": [
                    {
                        "id": "05_Icon_General_Close_Default_001",
                        "category": "Icon_General",
                        "semantic_name": "Close",
                        "state": "Default",
                        "output": "final/Icon_General/close.png",
                        "source_run": "bag-run",
                        "width": 128,
                        "height": 128,
                    }
                ],
            }
            (project_dir / "ui-asset-catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
            analysis = self.analysis(canonical)
            analysis["screens"][0]["assets"] = [{"category": "Panel", "semantic_name": "MainBag"}]

            result = INTAKE.compile_intake(project_dir, analysis)

            self.assertEqual(result["generate_count"], 2)
            self.assertEqual(result["reuse_count"], 1)
            inventory = json.loads((project_dir / "ui-resource-inventory.json").read_text(encoding="utf-8"))
            reused = next(item for item in inventory["assets"] if item["action"] == "reuse")
            self.assertEqual(reused["reuse_asset_id"], "05_Icon_General_Close_Default_001")
            self.assertEqual(reused["screen_size"], [1600, 900])

    def test_rejects_unconfirmed_layout_or_missing_difference_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_dir = Path(temporary_directory)
            canonical = project_dir / "canonical-style.png"
            canonical.write_bytes(b"fixture")
            analysis = self.analysis(canonical)
            analysis["screens"][0]["layout_confirmed"] = False
            with self.assertRaisesRegex(ValueError, "layout_confirmed"):
                INTAKE.compile_intake(project_dir, analysis)
            analysis["screens"][0]["layout_confirmed"] = True
            analysis["screens"][1]["difference_notes"] = ""
            with self.assertRaisesRegex(ValueError, "difference_notes"):
                INTAKE.compile_intake(project_dir, analysis)

    def test_catalog_merge_uses_semantic_identity_not_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "project_id": "xianxia-ui",
                        "assets": [
                            {
                                "id": "05_Icon_General_Close_Default_001",
                                "category": "Icon_General",
                                "semantic_name": "Close",
                                "state": "Default",
                                "output": "final/Icon_General/close.png",
                                "width": 128,
                                "height": 128,
                                "qa": "pass",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            catalog = root / "ui-asset-catalog.json"
            first = CATALOG.update_catalog(catalog, manifest, "run-01")
            self.assertEqual(first["added"], 1)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["assets"][0]["width"] = 256
            payload["assets"][0]["height"] = 256
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            second = CATALOG.update_catalog(catalog, manifest, "run-02")
            self.assertEqual(second["added"], 0)
            self.assertEqual(second["updated"], 1)
            stored = json.loads(catalog.read_text(encoding="utf-8"))["assets"]
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0]["width"], 256)


if __name__ == "__main__":
    unittest.main()
