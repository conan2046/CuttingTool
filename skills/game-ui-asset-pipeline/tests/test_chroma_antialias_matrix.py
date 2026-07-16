import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
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


CHROMA = load_module("remove_chroma_key")
VALIDATE = load_module("validate_asset_pack")


class ChromaAntialiasMatrixTest(unittest.TestCase):
    CASES = (
        ("GoldOnGreen", (0, 255, 0), (218, 165, 32)),
        ("WhiteOnMagenta", (255, 0, 255), (248, 248, 248)),
        ("DarkOnGreen", (0, 255, 0), (18, 22, 30)),
    )

    def antialiased_circle(
        self,
        key: tuple[int, int, int],
        fill: tuple[int, int, int],
        background: tuple[int, int, int] | None = None,
    ) -> Image.Image:
        large = Image.new("RGB", (256, 256), background or key)
        ImageDraw.Draw(large).ellipse((48, 48, 208, 208), fill=fill)
        return large.resize((64, 64), Image.Resampling.LANCZOS)

    def test_gold_white_dark_antialias_matrix_passes(self) -> None:
        for name, key, fill in self.CASES:
            with self.subTest(name=name):
                source = self.antialiased_circle(key, fill)
                diagnostics = CHROMA.recommend_chroma_thresholds(source, key)
                self.assertTrue(diagnostics["auto_apply"], diagnostics)
                output, report = CHROMA.remove_chroma(
                    source,
                    key,
                    diagnostics["suggested_transparent_threshold"],
                    diagnostics["suggested_opaque_threshold"],
                )
                self.assertTrue(report["ok"], report)
                self.assertGreater(report["partial_alpha_pixels"], 0)
                self.assertEqual(output.getpixel((0, 0)), (0, 0, 0, 0))
                self.assertEqual(output.getpixel((32, 32))[3], 255)
                array = np.asarray(output)
                visible_edge = (array[:, :, 3] >= 16) & (array[:, :, 3] < 240)
                edge_colors = array[:, :, :3][visible_edge].astype(np.int16)
                expected = np.asarray(fill, dtype=np.int16)
                self.assertLessEqual(int(np.max(np.abs(edge_colors - expected))), 18)
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    filename = f"06_Icon_Item_{name}_Default_001.png"
                    output.save(root / filename)
                    manifest = {
                        "expected_count": 1,
                        "assets": [
                            {
                                "category": "Icon_Item",
                                "category_index": 1,
                                "output": filename,
                                "width": 64,
                                "height": 64,
                            }
                        ],
                    }
                    qa = VALIDATE.validate_pack(manifest, root, {"chroma_key": CHROMA.format_hex(key)})
                    self.assertTrue(qa["ok"], qa)

    def test_shifted_generated_background_gets_adaptive_thresholds(self) -> None:
        key = (0, 255, 0)
        source = self.antialiased_circle(key, (218, 165, 32), background=(7, 246, 6))
        diagnostics = CHROMA.recommend_chroma_thresholds(source, key)
        self.assertTrue(diagnostics["auto_apply"], diagnostics)
        self.assertGreater(diagnostics["suggested_transparent_threshold"], 12)
        output, report = CHROMA.remove_chroma(
            source,
            key,
            diagnostics["suggested_transparent_threshold"],
            diagnostics["suggested_opaque_threshold"],
        )
        self.assertTrue(report["ok"], report)
        self.assertEqual(output.getpixel((0, 0)), (0, 0, 0, 0))

    def test_near_key_subject_blocks_adaptive_application(self) -> None:
        key = (0, 255, 0)
        source = self.antialiased_circle(key, (8, 220, 18))
        diagnostics = CHROMA.recommend_chroma_thresholds(source, key)
        self.assertFalse(diagnostics["auto_apply"], diagnostics)
        self.assertTrue(diagnostics["near_key_subject_risk"])
        self.assertIn("near-key-subject-risk", {issue["code"] for issue in diagnostics["issues"]})

    def test_heavily_polluted_border_is_low_confidence(self) -> None:
        source = Image.new("RGB", (64, 64), (0, 255, 0))
        draw = ImageDraw.Draw(source)
        draw.rectangle((0, 0, 63, 7), fill=(120, 120, 20))
        draw.rectangle((0, 56, 63, 63), fill=(20, 80, 160))
        diagnostics = CHROMA.recommend_chroma_thresholds(source, (0, 255, 0))
        self.assertEqual(diagnostics["confidence"], "low")
        self.assertFalse(diagnostics["auto_apply"])
        self.assertIn("unsafe-adaptive-thresholds", {issue["code"] for issue in diagnostics["issues"]})


if __name__ == "__main__":
    unittest.main()
