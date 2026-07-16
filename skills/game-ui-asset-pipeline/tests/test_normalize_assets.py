import importlib.util
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


SKILL_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_DIR / "scripts" / "normalize_assets.py"
SPEC = importlib.util.spec_from_file_location("normalize_assets", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class NormalizeAssetsTest(unittest.TestCase):
    def test_centers_asset_without_upscaling(self) -> None:
        source = Image.new("RGBA", (80, 100), (0, 0, 0, 0))
        ImageDraw.Draw(source).rectangle((20, 20, 59, 79), fill=(200, 80, 20, 255))
        output, metadata = MODULE.normalize_image(
            source,
            target_size=(128, 128),
            padding=8,
            alignment="center",
        )
        self.assertEqual(output.size, (128, 128))
        self.assertFalse(metadata["upscaled"])
        self.assertEqual(metadata["content_size"], [40, 60])
        self.assertEqual(output.getpixel((64, 64))[3], 255)
        self.assertEqual(output.getpixel((0, 0)), (0, 0, 0, 0))

    def test_scales_large_asset_down_once(self) -> None:
        source = Image.new("RGBA", (300, 200), (20, 100, 220, 255))
        output, metadata = MODULE.normalize_image(
            source,
            target_size=(128, 128),
            padding=8,
            alignment="center",
        )
        self.assertEqual(output.size, (128, 128))
        self.assertLess(metadata["scale"], 1.0)
        self.assertLessEqual(metadata["content_size"][0], 112)
        self.assertLessEqual(metadata["content_size"][1], 112)

    def test_bottom_alignment_uses_bottom_padding(self) -> None:
        source = Image.new("RGBA", (20, 30), (255, 255, 255, 255))
        output, metadata = MODULE.normalize_image(
            source,
            target_size=(64, 64),
            padding=6,
            alignment="bottom-center",
        )
        self.assertEqual(metadata["content_position"][1] + metadata["content_size"][1], 58)
        self.assertEqual(output.getpixel((32, 57))[3], 255)


if __name__ == "__main__":
    unittest.main()
