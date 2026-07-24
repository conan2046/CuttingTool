import importlib.util
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


CONTACT = load_module("make_contact_sheet")
VALIDATE = load_module("validate_asset_pack")


class DeliveryQaTest(unittest.TestCase):
    def create_pack(self, root: Path):
        entries = []
        for index, color in enumerate(((200, 40, 30, 255), (30, 80, 220, 255)), start=1):
            name = f"06_Icon_Item_Test{index}_Default_{index:03d}.png"
            image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
            ImageDraw.Draw(image).ellipse((16, 16, 111, 111), fill=color)
            image.save(root / name)
            entries.append(
                {
                    "id": Path(name).stem,
                    "category": "Icon_Item",
                    "semantic_name": f"Test{index}",
                    "state": "Default",
                    "output": name,
                    "width": 128,
                    "height": 128,
                    "qa": "pass",
                }
            )
        return {
            "schema_version": 1,
            "project_id": "qa-test",
            "category": "Icon_Item",
            "expected_count": 2,
            "assets": entries,
        }

    def test_valid_pack_and_contact_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = self.create_pack(root)
            request = {"chroma_key": "#00FF00"}
            report = VALIDATE.validate_pack(manifest, root, request)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["quality"]["score"], 100)
            self.assertEqual(report["quality"]["hard_blocker_count"], 0)
            self.assertEqual(len(report["quality"]["assets"]), 2)
            contact_path = root / "contact-sheet.png"
            contact = CONTACT.make_contact_sheet(manifest, root, contact_path, columns=2)
            self.assertTrue(contact["ok"])
            with Image.open(contact_path) as image:
                self.assertGreater(image.width, 0)
                self.assertGreater(image.height, 0)

    def test_hidden_rgb_under_zero_alpha_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = self.create_pack(root)
            path = root / manifest["assets"][0]["output"]
            with Image.open(path) as image:
                array = bytearray(image.convert("RGBA").tobytes())
            array[0:4] = bytes((255, 0, 0, 0))
            corrupted = Image.frombytes("RGBA", (128, 128), bytes(array))
            corrupted.save(path)
            report = VALIDATE.validate_pack(manifest, root, {"chroma_key": "#00FF00"})
            self.assertFalse(report["ok"])
            self.assertIn("hidden-rgb-under-zero-alpha", {issue["code"] for issue in report["issues"]})

    def test_sub_visible_chroma_resample_pixel_does_not_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = self.create_pack(root)
            path = root / manifest["assets"][0]["output"]
            with Image.open(path) as image:
                rgba = image.convert("RGBA")
            rgba.putpixel((8, 8), (0, 255, 0, 12))
            rgba.save(path)
            report = VALIDATE.validate_pack(manifest, root, {"chroma_key": "#00FF00"})
            self.assertTrue(report["ok"], report)

    def test_visible_chroma_residue_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = self.create_pack(root)
            path = root / manifest["assets"][0]["output"]
            with Image.open(path) as image:
                rgba = image.convert("RGBA")
            rgba.putpixel((8, 8), (0, 255, 0, 64))
            rgba.save(path)
            report = VALIDATE.validate_pack(manifest, root, {"chroma_key": "#00FF00"})
            self.assertFalse(report["ok"])
            self.assertIn("visible-chroma-residue", {issue["code"] for issue in report["issues"]})
            self.assertEqual(report["quality"]["status"], "blocked")

    def test_visible_chroma_spill_band_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = self.create_pack(root)
            path = root / manifest["assets"][0]["output"]
            with Image.open(path) as image:
                rgba = image.convert("RGBA")
            for x in range(8, 28):
                rgba.putpixel((x, 8), (200, 50, 200, 64))
            rgba.save(path)
            report = VALIDATE.validate_pack(manifest, root, {"chroma_key": "#FF00FF"})
            self.assertFalse(report["ok"])
        self.assertIn("visible-chroma-spill", {issue["code"] for issue in report["issues"]})

    def test_visible_internal_chroma_spill_fails_even_away_from_transparency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            filename = "06_Icon_Item_InternalSpill_Default_001.png"
            image = Image.new("RGBA", (64, 64), (120, 90, 40, 255))
            draw = ImageDraw.Draw(image)
            draw.rectangle((24, 24, 39, 39), fill=(15, 180, 20, 255))
            image.save(root / filename)
            manifest = {
                "expected_count": 1,
                "assets": [
                    {
                        "category": "Icon_Item",
                        "category_index": 1,
                        "output": filename,
                        "width": 64,
                        "height": 64,
                        "chroma_key": "#00FF00",
                    }
                ],
            }
            report = VALIDATE.validate_pack(manifest, root)
        self.assertFalse(report["ok"], report)
        self.assertIn("visible-chroma-spill", {issue["code"] for issue in report["issues"]})

    def test_non_continuous_category_indices_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = self.create_pack(root)
            manifest["assets"][0]["category_index"] = 1
            manifest["assets"][1]["category_index"] = 3
            report = VALIDATE.validate_pack(manifest, root, {"chroma_key": "#00FF00"})
            self.assertFalse(report["ok"])
            self.assertIn("non-continuous-category-indices", {issue["code"] for issue in report["issues"]})

    def panel_manifest(self, filename: str, width: int, height: int) -> dict:
        return {
            "expected_count": 1,
            "assets": [
                {
                    "id": Path(filename).stem,
                    "category": "Panel",
                    "category_index": 1,
                    "output": filename,
                    "width": width,
                    "height": height,
                }
            ],
        }

    def button_manifest(self, filename: str, width: int, height: int) -> dict:
        manifest = self.panel_manifest(filename, width, height)
        manifest["assets"][0]["category"] = "Button"
        return manifest

    def test_panel_with_plain_middle_stretch_bands_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            filename = "01_Panel_Plain_Default_001.png"
            image = Image.new("RGBA", (320, 180), (0, 0, 0, 0))
            ImageDraw.Draw(image).rectangle((20, 20, 299, 159), fill=(170, 210, 235, 255), outline=(240, 245, 250, 255), width=4)
            image.save(root / filename)
            report = VALIDATE.validate_pack(self.panel_manifest(filename, 320, 180), root)
            self.assertTrue(report["ok"], report)
            self.assertTrue(report["panel_stretch_bands"][0]["ok"])

    def test_panel_mid_edge_decorations_are_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            filename = "01_Panel_Decorated_Default_001.png"
            image = Image.new("RGBA", (320, 180), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.rectangle((20, 20, 299, 159), fill=(170, 210, 235, 255), outline=(240, 245, 250, 255), width=4)
            draw.polygon(((160, 6), (174, 20), (160, 34), (146, 20)), fill=(250, 220, 90, 255))
            draw.polygon(((160, 145), (174, 159), (160, 173), (146, 159)), fill=(250, 220, 90, 255))
            draw.polygon(((6, 90), (20, 76), (34, 90), (20, 104)), fill=(250, 220, 90, 255))
            draw.polygon(((285, 90), (299, 76), (313, 90), (299, 104)), fill=(250, 220, 90, 255))
            image.save(root / filename)
            report = VALIDATE.validate_pack(self.panel_manifest(filename, 320, 180), root)
            self.assertFalse(report["ok"])
            issue = next(issue for issue in report["issues"] if issue["code"] == "panel-stretch-band-decoration")
            self.assertEqual(set(issue["failed_edges"]), {"top", "bottom", "left", "right"})
            self.assertEqual(issue["severity"], "fail")

    def test_internal_edge_texture_is_detected_without_silhouette_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            filename = "01_Panel_InternalPattern_Default_001.png"
            image = Image.new("RGBA", (320, 180), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.rectangle((20, 20, 299, 159), fill=(170, 210, 235, 255), outline=(240, 245, 250, 255), width=4)
            draw.polygon(((24, 90), (34, 80), (44, 90), (34, 100)), fill=(250, 210, 80, 255))
            image.save(root / filename)
            report = VALIDATE.validate_pack(self.panel_manifest(filename, 320, 180), root)
            self.assertFalse(report["ok"])
            issue = next(issue for issue in report["issues"] if issue["code"] == "panel-stretch-band-decoration")
            left = next(edge for edge in issue["edge_reports"] if edge["edge"] == "left")
            self.assertTrue(left["silhouette_ok"])
            self.assertFalse(left["texture_ok"])

    def test_button_internal_edge_pattern_is_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            filename = "02_Button_Pattern_Normal_001.png"
            image = Image.new("RGBA", (320, 120), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.rectangle((20, 20, 299, 99), fill=(170, 210, 235, 255), outline=(240, 245, 250, 255), width=4)
            draw.polygon(((24, 60), (44, 35), (64, 60), (44, 85)), fill=(250, 210, 80, 255))
            image.save(root / filename)
            report = VALIDATE.validate_pack(self.button_manifest(filename, 320, 120), root)
            self.assertFalse(report["ok"])
            issue = next(issue for issue in report["issues"] if issue["code"] == "button-stretch-band-decoration")
            self.assertIn("left", issue["failed_edges"])

    def test_button_plain_beveled_material_gradient_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            filename = "02_Button_PlainGradient_Normal_001.png"
            image = Image.new("RGBA", (320, 120), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            for y in range(20, 100):
                blend = abs(60 - y) / 40.0
                color = (
                    int(165 + 18 * blend),
                    int(205 + 16 * blend),
                    int(230 + 12 * blend),
                    255,
                )
                draw.line((20, y, 299, y), fill=color)
            draw.rectangle((20, 20, 299, 99), outline=(240, 245, 250, 255), width=4)
            image.save(root / filename)

            report = VALIDATE.validate_pack(self.button_manifest(filename, 320, 120), root)

            self.assertTrue(report["ok"], report)

    def test_panel_with_empty_middle_profile_fails_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            filename = "01_Panel_Gapped_Default_001.png"
            image = Image.new("RGBA", (320, 180), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.rectangle((20, 20, 299, 159), fill=(170, 210, 235, 255))
            draw.rectangle((155, 0, 165, 179), fill=(0, 0, 0, 0))
            image.save(root / filename)

            report = VALIDATE.validate_pack(self.panel_manifest(filename, 320, 180), root)

            self.assertFalse(report["ok"])
            issue = next(issue for issue in report["issues"] if issue["code"] == "panel-stretch-band-decoration")
            top = next(edge for edge in issue["edge_reports"] if edge["edge"] == "top")
            self.assertGreater(top["gap_positions"], 0)
            self.assertFalse(top["silhouette_ok"])


if __name__ == "__main__":
    unittest.main()
