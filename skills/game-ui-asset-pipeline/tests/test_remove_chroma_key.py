import importlib.util
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / "scripts" / "remove_chroma_key.py"
SPEC = importlib.util.spec_from_file_location("remove_chroma_key", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RemoveChromaKeyTest(unittest.TestCase):
    def test_removes_green_background_and_preserves_subject(self) -> None:
        source = Image.new("RGB", (128, 128), "#00FF00")
        draw = ImageDraw.Draw(source)
        draw.rectangle((32, 24, 95, 103), fill="#B52A21")
        output, report = MODULE.remove_chroma(source, (0, 255, 0))
        self.assertEqual(output.mode, "RGBA")
        self.assertEqual(output.getpixel((0, 0)), (0, 0, 0, 0))
        self.assertEqual(output.getpixel((64, 64))[3], 255)
        self.assertTrue(report["ok"])

    def test_soft_edge_is_partial_alpha_without_key_residue(self) -> None:
        large = Image.new("RGB", (256, 256), "#00FF00")
        draw = ImageDraw.Draw(large)
        draw.ellipse((48, 48, 208, 208), fill="#D97706")
        source = large.resize((64, 64), Image.Resampling.LANCZOS)
        output, report = MODULE.remove_chroma(source, (0, 255, 0))
        alpha_histogram = output.getchannel("A").histogram()
        self.assertTrue(any(alpha_histogram[1:255]))
        self.assertEqual(report["visible_near_key_pixels"], 0)

    def test_rejects_invalid_threshold_order(self) -> None:
        source = Image.new("RGB", (16, 16), "#00FF00")
        with self.assertRaises(ValueError):
            MODULE.remove_chroma(source, (0, 255, 0), transparent_threshold=100, opaque_threshold=50)


if __name__ == "__main__":
    unittest.main()
