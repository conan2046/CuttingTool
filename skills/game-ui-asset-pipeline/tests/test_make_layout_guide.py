import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / "scripts" / "make_layout_guide.py"
SPEC = importlib.util.spec_from_file_location("make_layout_guide", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class LayoutGuideTest(unittest.TestCase):
    def test_creates_expected_slot_count_and_image_size(self) -> None:
        spec = MODULE.LayoutSpec(width=2048, height=2048, columns=4, rows=4)
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "guide.png"
            payload = MODULE.render_layout_guide(spec, output)
            self.assertEqual(len(payload["slots"]), 16)
            with Image.open(output) as image:
                self.assertEqual(image.size, (2048, 2048))

    def test_rejects_safe_padding_that_erases_slot(self) -> None:
        spec = MODULE.LayoutSpec(
            width=512,
            height=512,
            columns=4,
            rows=4,
            outer_margin=32,
            gutter=16,
            safe_padding=80,
        )
        with self.assertRaises(ValueError):
            MODULE.calculate_slots(spec)


if __name__ == "__main__":
    unittest.main()
