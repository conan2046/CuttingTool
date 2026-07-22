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
    def test_normalizes_composed_prefab_and_mutual_view_toggle(self) -> None:
        layout = {
            "schema_version": 1,
            "screens": [
                {"id": "LeftSection", "reference_size": [1920, 1080], "elements": [{"id": "LeftPanel", "kind": "Image"}]},
                {"id": "AttributeSection", "reference_size": [1920, 1080], "elements": [{"id": "AttributePanel", "kind": "Image"}]},
                {"id": "InventorySection", "reference_size": [1920, 1080], "elements": [{"id": "InventoryPanel", "kind": "Image"}]},
                {
                    "id": "CompositeScreen",
                    "reference_size": [1920, 1080],
                    "elements": [
                        {"id": "Left", "kind": "PrefabInstance", "prefab_screen_id": "LeftSection", "size": [1920, 1080]},
                        {"id": "Attributes", "kind": "PrefabInstance", "prefab_screen_id": "AttributeSection", "size": [1920, 1080]},
                        {"id": "Inventory", "kind": "PrefabInstance", "prefab_screen_id": "InventorySection", "size": [1920, 1080]},
                        {"id": "ShowAttributes", "kind": "Button"},
                        {"id": "ShowInventory", "kind": "Button"},
                    ],
                    "toggle_groups": [{
                        "id": "RightPanelTabs",
                        "default_target_id": "Attributes",
                        "bindings": [
                            {"button_id": "ShowAttributes", "target_id": "Attributes"},
                            {"button_id": "ShowInventory", "target_id": "Inventory"},
                        ],
                    }],
                },
            ],
        }
        screens = UNITY_EXPORT.normalize_layout(layout)
        self.assertEqual(screens[3]["elements"][0]["prefab_screen_id"], "LeftSection")
        self.assertEqual(screens[3]["toggle_groups"][0]["default_target_id"], "Attributes")

    def test_rejects_prefab_instance_that_references_later_screen(self) -> None:
        layout = {
            "schema_version": 1,
            "screens": [
                {"id": "Composite", "reference_size": [1920, 1080], "elements": [{"id": "Later", "kind": "PrefabInstance", "prefab_screen_id": "LaterScreen"}]},
                {"id": "LaterScreen", "reference_size": [1920, 1080], "elements": [{"id": "Panel", "kind": "Image"}]},
            ],
        }
        with self.assertRaisesRegex(ValueError, "must reference an earlier screen"):
            UNITY_EXPORT.normalize_layout(layout)

    def test_infers_high_confidence_frame_border(self) -> None:
        result = NINE_SLICE.infer_nine_slice(frame_image())
        self.assertTrue(result["apply"], result)
        self.assertGreaterEqual(result["confidence"], 0.65)
        for value in result["border"]:
            self.assertGreaterEqual(value, 4)
            self.assertLess(value, 58)

    def test_derives_ppu_from_smallest_layout_scale(self) -> None:
        ppu, scale = UNITY_EXPORT.derive_pixels_per_unit(
            (971, 412),
            [[1880, 120], [350, 92]],
            100.0,
        )
        self.assertAlmostEqual(scale, 92 / 412, places=6)
        self.assertAlmostEqual(ppu, 100 / (92 / 412), places=3)

    def test_sliced_geometry_rejects_border_larger_than_target_at_ppu(self) -> None:
        issues = UNITY_EXPORT.validate_sliced_layout_geometry(
            "QuestRow",
            [180, 95, 180, 95],
            100.0,
            [[1880, 120]],
        )
        self.assertEqual(issues[0]["code"], "nine-slice-border-exceeds-layout-size")
        self.assertEqual(issues[0]["border_units"], [360.0, 190.0])
        self.assertEqual(
            UNITY_EXPORT.validate_sliced_layout_geometry(
                "QuestRow", [180, 95, 180, 95], 448.0, [[1880, 120]]
            ),
            [],
        )

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
            self.assertEqual(plan["sprites"][0]["pixels_per_unit_origin"], "layout-derived")
            self.assertEqual(plan["sprites"][0]["pixels_per_unit"], 100.0)
            self.assertEqual(
                plan["sprites"][0]["asset_path"],
                "Assets/_Project/UI/Sprites/commercial-ui/01_Panel_Main_Default_001.png",
            )
            self.assertEqual(plan["screen_prefab_root"], "Assets/_Project/Prefabs/UI/Demo")
            self.assertEqual(plan["scene_root"], "Assets/_Project/Scenes/Demo")
            self.assertNotIn("create_asset_prefabs", plan)
            self.assertEqual(plan["screens"][0]["elements"][0]["id"], "MainPanel")
            rollback = json.loads((run_dir / "unity" / "unity-rollback.json").read_text(encoding="utf-8"))
            self.assertEqual(rollback["sprite_export_root"], "Assets/_Project/UI/Sprites/commercial-ui")
            self.assertIn("Assets/_Project/Prefabs/UI/Demo/main-screen.prefab", rollback["created_assets"])
            demo_prefabs = unity_project / "Assets" / "_Project" / "Prefabs" / "UI" / "Demo"
            demo_prefabs.mkdir(parents=True)
            (demo_prefabs / "main-screen.prefab").write_text("generated", encoding="utf-8")
            (demo_prefabs / "Keep.prefab").write_text("handmade", encoding="utf-8")
            demo_scenes = unity_project / "Assets" / "_Project" / "Scenes" / "Demo"
            demo_scenes.mkdir(parents=True)
            (demo_scenes / "main-screen-Preview.unity").write_text("generated", encoding="utf-8")
            rollback_result = UNITY_ROLLBACK.rollback(run_dir / "unity" / "unity-rollback.json")
            self.assertTrue(rollback_result["ok"])
            self.assertFalse((unity_project / "Assets" / "_Project" / "UI" / "Sprites" / "commercial-ui").exists())
            self.assertFalse((demo_prefabs / "main-screen.prefab").exists())
            self.assertTrue((demo_prefabs / "Keep.prefab").is_file())
            self.assertFalse((demo_scenes / "main-screen-Preview.unity").exists())
            self.assertTrue((unity_project / "Packages" / "com.hongda.game-ui-asset-pipeline").is_dir())

    def test_prepares_two_screen_prefabs_sharing_one_sprite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir = root / "run"
            unity_project = root / "UnityProject"
            (unity_project / "Assets").mkdir(parents=True)
            (unity_project / "Packages").mkdir()
            (unity_project / "ProjectSettings").mkdir()
            (unity_project / "ProjectSettings" / "ProjectVersion.txt").write_text(
                "m_EditorVersion: 2022.3.62f1\n", encoding="utf-8"
            )
            asset_id = "05_Icon_General_Close_Default_001"
            asset_path = run_dir / "final" / "Icon_General" / f"{asset_id}.png"
            asset_path.parent.mkdir(parents=True)
            Image.new("RGBA", (64, 64), (220, 230, 255, 255)).save(asset_path)
            manifest = {
                "schema_version": 2,
                "project_id": "multi-screen-ui",
                "assets": [
                    {
                        "id": asset_id,
                        "category": "Icon_General",
                        "semantic_name": "Close",
                        "state": "Default",
                        "output": f"final/Icon_General/{asset_id}.png",
                        "width": 64,
                        "height": 64,
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
                        "id": "BagScreen",
                        "reference_size": [1920, 1080],
                        "elements": [{"id": "Close", "kind": "Image", "asset_id": asset_id, "size": [64, 64]}],
                    },
                    {
                        "id": "ShopScreen",
                        "reference_size": [1600, 900],
                        "elements": [{"id": "Close", "kind": "Image", "asset_id": asset_id, "size": [48, 48]}],
                    },
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
            self.assertEqual(result["screen_count"], 2)
            plan = json.loads((run_dir / "unity" / "unity-import-plan.json").read_text(encoding="utf-8"))
            self.assertEqual([screen["id"] for screen in plan["screens"]], ["BagScreen", "ShopScreen"])
            rollback = json.loads((run_dir / "unity" / "unity-rollback.json").read_text(encoding="utf-8"))
            self.assertIn("Assets/_Project/Prefabs/UI/Demo/BagScreen.prefab", rollback["created_assets"])
            self.assertIn("Assets/_Project/Prefabs/UI/Demo/ShopScreen.prefab", rollback["created_assets"])
            self.assertIn("Assets/_Project/Scenes/Demo/BagScreen-Preview.unity", rollback["created_assets"])
            self.assertIn("Assets/_Project/Scenes/Demo/ShopScreen-Preview.unity", rollback["created_assets"])

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
        self.assertIn("CreatePreviewScenes(plan, issues, out var previewImageCount)", importer)
        self.assertIn("Selectable.Transition.SpriteSwap", importer)
        self.assertIn("asset_prefab_count = 0", importer)
        self.assertNotIn("CreateAssetPrefabs(plan", importer)
        self.assertIn("RemoveLegacyAssetPrefabs(plan, issues)", importer)

    def test_rejects_missing_or_failed_formal_qa(self) -> None:
        source = (SCRIPTS_DIR / "prepare_unity_export.py").read_text(encoding="utf-8")
        self.assertIn("formal QA report not found", source)
        self.assertIn("formal QA has unresolved failures", source)

    def test_normalizes_color_and_button_sprite_states(self) -> None:
        layout = {
            "schema_version": 1,
            "screens": [
                {
                    "id": "interactive",
                    "reference_size": [1980, 1080],
                    "elements": [
                        {"id": "Background", "kind": "Image", "color": [0.1, 0.2, 0.3, 1.0]},
                        {
                            "id": "Action",
                            "kind": "Button",
                            "asset_id": "Normal",
                            "highlighted_asset_id": "Hover",
                            "pressed_asset_id": "Pressed",
                            "disabled_asset_id": "Disabled",
                        },
                    ],
                }
            ],
        }
        elements = UNITY_EXPORT.normalize_layout(layout)[0]["elements"]
        self.assertEqual(elements[0]["color"], [0.1, 0.2, 0.3, 1.0])
        self.assertEqual(elements[1]["highlighted_asset_id"], "Hover")
        self.assertEqual(elements[1]["pressed_asset_id"], "Pressed")
        self.assertEqual(elements[1]["disabled_asset_id"], "Disabled")

    def test_normalizes_text_element_with_tmp_font_paths(self) -> None:
        layout = {
            "schema_version": 1,
            "screens": [{
                "id": "TextScreen",
                "reference_size": [1920, 1080],
                "elements": [{
                    "id": "ConfirmLabel",
                    "kind": "Text",
                    "text": "确认",
                    "size": [200, 60],
                    "font_size": 34,
                    "text_alignment": "Center",
                    "font_style": "Bold",
                    "enable_auto_sizing": True,
                    "font_source_path": "Assets/_Project/UI/Fonts/NotoSansSC-VF.ttf",
                    "font_asset_path": "Assets/_Project/UI/Fonts/NotoSansSC-VF SDF.asset",
                }],
            }],
        }
        element = UNITY_EXPORT.normalize_layout(layout)[0]["elements"][0]
        self.assertEqual(element["text"], "确认")
        self.assertEqual(element["font_style"], "Bold")
        self.assertTrue(element["enable_auto_sizing"])

    def test_allows_project_default_tmp_font_when_text_has_no_font_paths(self) -> None:
        base = {
            "schema_version": 1,
            "screens": [{
                "id": "TextScreen",
                "reference_size": [1920, 1080],
                "elements": [{"id": "Label", "kind": "Text"}],
            }],
        }
        with self.assertRaisesRegex(ValueError, "text must be non-empty"):
            UNITY_EXPORT.normalize_layout(base)
        base["screens"][0]["elements"][0]["text"] = "Label"
        element = UNITY_EXPORT.normalize_layout(base)[0]["elements"][0]
        self.assertEqual(element["font_source_path"], "")
        self.assertEqual(element["font_asset_path"], "")

    def test_rejects_incomplete_text_font_override(self) -> None:
        layout = {"schema_version": 1, "screens": [{"id": "TextScreen", "reference_size": [1920, 1080], "elements": [{"id": "Label", "kind": "Text", "text": "确认", "font_source_path": "Assets/_Project/UI/Fonts/Custom.otf"}]}]}
        with self.assertRaisesRegex(ValueError, "must be provided together"):
            UNITY_EXPORT.normalize_layout(layout)

    def test_normalizes_layout_group_configuration(self) -> None:
        layout = {
            "schema_version": 1,
            "screens": [
                {
                    "id": "Inventory",
                    "reference_size": [1920, 1080],
                    "elements": [
                        {
                            "id": "SlotGrid",
                            "kind": "GridLayoutGroup",
                            "size": [772, 772],
                            "cell_size": [132, 132],
                            "spacing": [28, 28],
                            "constraint": "FixedColumnCount",
                            "constraint_count": 5,
                            "start_axis": "Horizontal",
                            "child_alignment": "MiddleCenter",
                        },
                        {
                            "id": "Slot01",
                            "parent_id": "SlotGrid",
                            "kind": "Image",
                            "asset_id": "Slot",
                        },
                    ],
                }
            ],
        }
        elements = UNITY_EXPORT.normalize_layout(layout)[0]["elements"]
        self.assertEqual(elements[0]["kind"], "GridLayoutGroup")
        self.assertEqual(elements[0]["cell_size"], [132.0, 132.0])
        self.assertEqual(elements[0]["spacing"], [28.0, 28.0])
        self.assertEqual(elements[0]["constraint"], "FixedColumnCount")
        self.assertEqual(elements[0]["constraint_count"], 5)
        self.assertEqual(elements[1]["parent_id"], "SlotGrid")

    def test_rejects_invalid_layout_group_configuration(self) -> None:
        base = {
            "schema_version": 1,
            "screens": [{
                "id": "Inventory",
                "reference_size": [1920, 1080],
                "elements": [{
                    "id": "SlotGrid",
                    "kind": "GridLayoutGroup",
                    "size": [772, 772],
                }],
            }],
        }
        invalid_cases = {
            "start_axis": "Diagonal",
            "start_corner": "Center",
            "child_alignment": "Center",
            "child_control_size": [1, 0],
            "child_force_expand": [False],
        }
        for field_name, invalid_value in invalid_cases.items():
            with self.subTest(field_name=field_name):
                layout = json.loads(json.dumps(base))
                layout["screens"][0]["elements"][0][field_name] = invalid_value
                with self.assertRaises(ValueError):
                    UNITY_EXPORT.normalize_layout(layout)

    def test_normalizes_scroll_view_with_masked_grid_content(self) -> None:
        layout = {
            "schema_version": 1,
            "screens": [{
                "id": "Inventory",
                "reference_size": [1920, 1080],
                "elements": [
                    {"id": "InventoryScrollView", "kind": "ScrollView", "size": [772, 632], "viewport_id": "InventoryViewport", "content_id": "InventoryGrid", "vertical_scroll": True, "horizontal_scroll": False, "movement_type": "Clamped"},
                    {"id": "InventoryViewport", "parent_id": "InventoryScrollView", "kind": "ScrollViewport", "size": [772, 632]},
                    {"id": "InventoryGrid", "parent_id": "InventoryViewport", "kind": "GridLayoutGroup", "size": [772, 772], "cell_size": [132, 132], "spacing": [28, 28], "constraint": "FixedColumnCount", "constraint_count": 5, "content_size_fitter": True, "vertical_fit": "PreferredSize"},
                ],
            }],
        }
        elements = UNITY_EXPORT.normalize_layout(layout)[0]["elements"]
        self.assertEqual(elements[0]["viewport_id"], "InventoryViewport")
        self.assertEqual(elements[0]["content_id"], "InventoryGrid")
        self.assertTrue(elements[0]["vertical_scroll"])
        self.assertEqual(elements[0]["color"], [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(elements[2]["vertical_fit"], "PreferredSize")

    def test_rejects_scroll_view_without_valid_viewport_content_chain(self) -> None:
        layout = {
            "schema_version": 1,
            "screens": [{
                "id": "Inventory",
                "reference_size": [1920, 1080],
                "elements": [{"id": "InventoryScrollView", "kind": "ScrollView", "viewport_id": "MissingViewport", "content_id": "MissingContent"}],
            }],
        }
        with self.assertRaises(ValueError):
            UNITY_EXPORT.normalize_layout(layout)

    def test_rejects_out_of_range_layout_color(self) -> None:
        layout = {
            "schema_version": 1,
            "screens": [
                {
                    "id": "bad-color",
                    "reference_size": [100, 100],
                    "elements": [{"id": "Background", "kind": "Image", "color": [1, 1, 1, 2]}],
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            UNITY_EXPORT.normalize_layout(layout)


if __name__ == "__main__":
    unittest.main()
