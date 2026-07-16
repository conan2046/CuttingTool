import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


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

    def test_non_continuous_category_indices_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = self.create_pack(root)
            manifest["assets"][0]["category_index"] = 1
            manifest["assets"][1]["category_index"] = 3
            report = VALIDATE.validate_pack(manifest, root, {"chroma_key": "#00FF00"})
            self.assertFalse(report["ok"])
            self.assertIn("non-continuous-category-indices", {issue["code"] for issue in report["issues"]})


if __name__ == "__main__":
    unittest.main()
