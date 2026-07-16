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


LAYOUT = load_module("make_layout_guide")
CHROMA = load_module("remove_chroma_key")
EXTRACT = load_module("extract_sheet_assets")


class ExtractSheetAssetsTest(unittest.TestCase):
    def make_sheet(self, missing_last: bool = False):
        spec = LAYOUT.LayoutSpec(
            width=512,
            height=512,
            columns=2,
            rows=2,
            outer_margin=32,
            gutter=16,
            safe_padding=32,
        )
        slots = LAYOUT.calculate_slots(spec)
        source = Image.new("RGB", (512, 512), "#00FF00")
        draw = ImageDraw.Draw(source)
        colors = ["#B91C1C", "#1D4ED8", "#D97706", "#7E22CE"]
        for index, slot in enumerate(slots):
            if missing_last and index == 3:
                continue
            safe = slot["safe_box"]
            box = (safe["left"] + 12, safe["top"] + 12, safe["right"] - 12, safe["bottom"] - 12)
            if index == 0:
                draw.rectangle(box, fill=colors[index])
                inner = (box[0] + 24, box[1] + 24, box[2] - 24, box[3] - 24)
                draw.rectangle(inner, fill="#00FF00")
            else:
                draw.ellipse(box, fill=colors[index])
        alpha_sheet, _ = CHROMA.remove_chroma(source, (0, 255, 0))
        layout_payload = {"slots": slots, "layout": vars(spec)}
        request = {
            "project_id": "test-ui",
            "category": "Icon_Item",
            "assets": [
                {"semantic_name": "Frame", "state": "Default"},
                {"semantic_name": "ManaPotion", "state": "Default"},
                {"semantic_name": "Coin", "state": "Default"},
                {"semantic_name": "Crystal", "state": "Default"},
            ],
        }
        return alpha_sheet, layout_payload, request

    def test_extracts_four_assets_and_preserves_hollow_center(self) -> None:
        source, layout, request = self.make_sheet()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "assets"
            manifest, report = EXTRACT.extract_assets(source, layout, request, output_dir)
            self.assertTrue(report["ok"])
            self.assertEqual(manifest["exported_count"], 4)
            files = sorted(output_dir.glob("*.png"))
            self.assertEqual(len(files), 4)
            frame_path = next(path for path in files if "Frame" in path.name)
            with Image.open(frame_path) as frame:
                self.assertEqual(frame.mode, "RGBA")
                self.assertEqual(frame.getpixel((frame.width // 2, frame.height // 2))[3], 0)

    def test_reports_empty_slot_as_failure(self) -> None:
        source, layout, request = self.make_sheet(missing_last=True)
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest, report = EXTRACT.extract_assets(
                source,
                layout,
                request,
                Path(temporary_directory) / "assets",
            )
            self.assertFalse(report["ok"])
            self.assertEqual(manifest["exported_count"], 3)
            self.assertIn("empty-slot", {issue["code"] for issue in report["issues"]})

    def test_connected_components_uses_diagonal_connectivity(self) -> None:
        import numpy as np

        mask = np.zeros((4, 4), dtype=bool)
        mask[1, 1] = True
        mask[2, 2] = True
        components = EXTRACT.connected_components(mask)
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["pixels"], 2)

    def test_preserves_item_that_extends_into_layout_gutter(self) -> None:
        spec = LAYOUT.LayoutSpec(
            width=512,
            height=256,
            columns=2,
            rows=1,
            outer_margin=32,
            gutter=32,
            safe_padding=24,
        )
        slots = LAYOUT.calculate_slots(spec)
        source = Image.new("RGB", (512, 256), "#00FF00")
        draw = ImageDraw.Draw(source)
        first_slot = slots[0]["slot"]
        # Deliberately extend the valid isolated item into the guide gutter.
        draw.rectangle((80, 70, first_slot["right"] + 18, 190), fill="#B91C1C")
        draw.ellipse((330, 70, 450, 190), fill="#1D4ED8")
        alpha_sheet, _ = CHROMA.remove_chroma(source, (0, 255, 0))
        request = {
            "project_id": "gutter-test",
            "category": "Icon_Item",
            "assets": [
                {"semantic_name": "WideItem", "state": "Default"},
                {"semantic_name": "RoundItem", "state": "Default"},
            ],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest, report = EXTRACT.extract_assets(
                alpha_sheet,
                {"slots": slots, "layout": vars(spec)},
                request,
                Path(temporary_directory) / "assets",
            )
        self.assertTrue(report["ok"])
        self.assertEqual(manifest["assignment_mode"], "global-components-nearest-slot-center")
        self.assertGreater(manifest["assets"][0]["source_bbox"][2], first_slot["right"])

    def test_merges_near_fragments_without_warning(self) -> None:
        source = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(source)
        draw.rectangle((80, 80, 150, 160), fill=(210, 130, 30, 255))
        draw.rectangle((156, 110, 170, 126), fill=(240, 190, 60, 255))
        layout = {"slots": [{"slot": {"left": 0, "top": 0, "right": 256, "bottom": 256}}]}
        request = {"project_id": "fragments", "category": "Icon_Item", "assets": [{"semantic_name": "Hammer"}]}
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest, report = EXTRACT.extract_assets(source, layout, request, Path(temporary_directory))
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["warning_count"], 0)
        self.assertEqual(manifest["assets"][0]["merged_component_count"], 2)
        self.assertEqual(manifest["assets"][0]["detached_component_count"], 0)

    def test_reports_far_and_major_detached_components(self) -> None:
        source = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(source)
        draw.rectangle((40, 80, 100, 160), fill=(210, 130, 30, 255))
        draw.rectangle((170, 85, 225, 155), fill=(40, 90, 210, 255))
        layout = {"slots": [{"slot": {"left": 0, "top": 0, "right": 256, "bottom": 256}}]}
        request = {"project_id": "fragments", "category": "Icon_Item", "assets": [{"semantic_name": "TwoItems"}]}
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest, report = EXTRACT.extract_assets(source, layout, request, Path(temporary_directory))
        codes = {issue["code"] for issue in report["issues"]}
        self.assertTrue(report["ok"], report)
        self.assertIn("detached-components", codes)
        self.assertIn("multiple-major-components", codes)
        self.assertEqual(manifest["assets"][0]["qa"], "warning")
        self.assertEqual(manifest["assets"][0]["major_detached_count"], 1)


if __name__ == "__main__":
    unittest.main()
