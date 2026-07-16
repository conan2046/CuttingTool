import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
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


CHROMA = load_module("remove_chroma_key")
EXTRACT = load_module("extract_sheet_assets")
LAYOUT = load_module("make_layout_guide")


class P4FailureMatrixTest(unittest.TestCase):
    def test_hard_edge_partial_opacity_survives_without_visible_spill(self) -> None:
        key = (0, 255, 0)
        source = Image.new("RGBA", (192, 192), (*key, 255))
        effect = Image.new("RGBA", source.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(effect)
        draw.ellipse((28, 28, 164, 164), fill=(255, 120, 20, 72))
        draw.ellipse((42, 42, 150, 150), fill=(255, 170, 30, 156))
        draw.ellipse((58, 58, 134, 134), fill=(255, 235, 180, 255))
        source = Image.alpha_composite(source, effect).convert("RGB")
        diagnostics = CHROMA.recommend_chroma_thresholds(source, key)
        self.assertTrue(diagnostics["auto_apply"], diagnostics)
        output, report = CHROMA.remove_chroma(
            source,
            key,
            diagnostics["suggested_transparent_threshold"],
            diagnostics["suggested_opaque_threshold"],
        )
        alpha = np.asarray(output)[:, :, 3]
        self.assertTrue(report["ok"], report)
        self.assertGreater(int(np.count_nonzero((alpha >= 16) & (alpha < 240))), 100)
        self.assertEqual(output.getpixel((0, 0)), (0, 0, 0, 0))

    def test_white_metal_highlight_and_dark_outline_are_preserved(self) -> None:
        for name, key, outer, inner in (
            ("white-metal", (255, 0, 255), (245, 245, 250), (150, 105, 35)),
            ("dark-outline", (0, 255, 0), (10, 12, 18), (45, 22, 72)),
        ):
            with self.subTest(name=name):
                source = Image.new("RGB", (192, 192), key)
                draw = ImageDraw.Draw(source)
                draw.ellipse((34, 34, 158, 158), fill=outer)
                draw.ellipse((50, 50, 142, 142), fill=inner)
                source = source.resize((128, 128), Image.Resampling.LANCZOS)
                diagnostics = CHROMA.recommend_chroma_thresholds(source, key)
                output, report = CHROMA.remove_chroma(
                    source,
                    key,
                    diagnostics["suggested_transparent_threshold"],
                    diagnostics["suggested_opaque_threshold"],
                )
                self.assertTrue(report["ok"], report)
                self.assertEqual(output.getpixel((64, 64))[:3], inner)
                self.assertEqual(output.getpixel((64, 64))[3], 255)

    def test_large_canvas_pixel_drift_is_safely_adapted(self) -> None:
        height = width = 1024
        y, x = np.indices((height, width))
        rgb = np.empty((height, width, 3), dtype=np.uint8)
        rgb[:, :, 0] = ((x * 7 + y * 3) % 11).astype(np.uint8)
        rgb[:, :, 1] = (245 + ((x * 5 + y * 2) % 11)).astype(np.uint8)
        rgb[:, :, 2] = ((x * 2 + y * 7) % 9).astype(np.uint8)
        rgb[320:704, 320:704] = (210, 135, 36)
        source = Image.fromarray(rgb, mode="RGB")
        diagnostics = CHROMA.recommend_chroma_thresholds(source, (0, 255, 0))
        self.assertTrue(diagnostics["auto_apply"], diagnostics)
        self.assertGreaterEqual(diagnostics["suggested_transparent_threshold"], 16)
        output, report = CHROMA.remove_chroma(
            source,
            (0, 255, 0),
            diagnostics["suggested_transparent_threshold"],
            diagnostics["suggested_opaque_threshold"],
        )
        self.assertTrue(report["ok"], report)
        self.assertEqual(output.getpixel((0, 0))[3], 0)
        self.assertEqual(output.getpixel((512, 512))[3], 255)

    def test_both_green_and_magenta_near_key_subjects_block_auto_apply(self) -> None:
        for key, subject in (((0, 255, 0), (8, 220, 18)), ((255, 0, 255), (220, 8, 220))):
            with self.subTest(key=key):
                source = Image.new("RGB", (128, 128), key)
                ImageDraw.Draw(source).ellipse((24, 24, 104, 104), fill=subject)
                diagnostics = CHROMA.recommend_chroma_thresholds(source, key)
                self.assertFalse(diagnostics["auto_apply"], diagnostics)
                self.assertTrue(diagnostics["near_key_subject_risk"], diagnostics)

    def test_noise_bridge_between_slots_is_explicit_failure(self) -> None:
        spec = LAYOUT.LayoutSpec(512, 256, 2, 1, 32, 32, 24)
        slots = LAYOUT.calculate_slots(spec)
        source = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(source)
        draw.rectangle((72, 72, 200, 184), fill=(180, 40, 30, 255))
        draw.rectangle((312, 72, 440, 184), fill=(40, 80, 200, 255))
        draw.line((200, 128, 312, 128), fill=(120, 120, 120, 255), width=1)
        request = {
            "project_id": "bridge",
            "category": "Icon_Item",
            "assets": [{"semantic_name": "Left"}, {"semantic_name": "Right"}],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            _, report = EXTRACT.extract_assets(
                source,
                {"slots": slots, "layout": vars(spec)},
                request,
                Path(temporary_directory),
                minimum_component_pixels=1,
            )
        self.assertFalse(report["ok"], report)
        self.assertIn("cross-slot-connected-component", {item["code"] for item in report["issues"]})

    def test_multiple_legal_detached_decorations_are_all_retained(self) -> None:
        source = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(source)
        draw.rectangle((72, 72, 164, 164), fill=(180, 40, 30, 255))
        for box in ((20, 30, 23, 33), (220, 40, 223, 43), (34, 220, 37, 223)):
            draw.rectangle(box, fill=(240, 180, 40, 255))
        request = {
            "project_id": "multi-decoration",
            "category": "Icon_Effect",
            "fragment_policy": {
                "detached_action": "allow-small",
                "small_detached_max_pixels": 20,
                "small_detached_max_anchor_ratio": 0.01,
            },
            "assets": [{"semantic_name": "BurstWithSparks"}],
        }
        layout = {"slots": [{"slot": {"left": 0, "top": 0, "right": 256, "bottom": 256}}]}
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest, report = EXTRACT.extract_assets(source, layout, request, Path(temporary_directory))
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["warning_count"], 0)
        self.assertEqual(manifest["assets"][0]["accepted_detached_count"], 3)


if __name__ == "__main__":
    unittest.main()
