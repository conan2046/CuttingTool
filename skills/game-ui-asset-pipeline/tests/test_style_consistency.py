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


STYLE = load_module("style_consistency")


class StyleConsistencyTest(unittest.TestCase):
    def write_asset(self, path: Path, fill: tuple[int, int, int], accent: tuple[int, int, int]) -> None:
        image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((12, 18, 84, 78), radius=12, fill=(*fill, 255), outline=(*accent, 255), width=5)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)

    def test_matching_blue_white_sheets_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical.png"
            self.write_asset(canonical, (190, 225, 245), (240, 205, 120))
            self.write_asset(root / "final/Panel/panel.png", (185, 220, 242), (235, 200, 116))
            self.write_asset(root / "final/Button/button.png", (195, 230, 248), (242, 208, 126))
            manifest = {"assets": [
                {"job_id": "panel-sheet-01", "output": "final/Panel/panel.png"},
                {"job_id": "button-sheet-01", "output": "final/Button/button.png"},
            ]}
            report = STYLE.evaluate_style_consistency(manifest, root, canonical, warning_below=70, fail_below=50)
            self.assertTrue(report["ok"])
            self.assertGreaterEqual(report["overall_score"], 70)
            self.assertEqual(report["issues"], [])

    def test_divergent_sheet_is_reported_with_job_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical.png"
            self.write_asset(canonical, (190, 225, 245), (240, 205, 120))
            self.write_asset(root / "final/Panel/panel.png", (188, 224, 246), (238, 203, 120))
            self.write_asset(root / "final/Button/button.png", (65, 8, 8), (150, 15, 15))
            manifest = {"assets": [
                {"job_id": "panel-sheet-01", "output": "final/Panel/panel.png"},
                {"job_id": "button-sheet-01", "output": "final/Button/button.png"},
            ]}
            report = STYLE.evaluate_style_consistency(manifest, root, canonical, warning_below=75, fail_below=65)
            issues = [issue for issue in report["issues"] if issue["job_id"] == "button-sheet-01"]
            self.assertTrue(issues)
            self.assertEqual(issues[0]["code"], "cross-sheet-style-drift")

    def test_empty_visible_profile_is_a_traced_failure_instead_of_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical.png"
            self.write_asset(canonical, (190, 225, 245), (240, 205, 120))
            self.write_asset(root / "final/Panel/panel.png", (188, 224, 246), (238, 203, 120))
            self.write_asset(root / "final/Nav/nav.png", (184, 219, 240), (232, 198, 112))
            empty = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
            empty.putpixel((256, 256), (255, 255, 255, 1))
            (root / "final/Button").mkdir(parents=True, exist_ok=True)
            empty.save(root / "final/Button/button.png")
            manifest = {"assets": [
                {"id": "panel", "job_id": "panel-sheet-01", "output": "final/Panel/panel.png"},
                {"id": "button", "job_id": "button-sheet-01", "output": "final/Button/button.png"},
                {"id": "nav", "job_id": "nav-sheet-01", "output": "final/Nav/nav.png"},
            ]}

            report = STYLE.evaluate_style_consistency(manifest, root, canonical, warning_below=70, fail_below=50)

            self.assertFalse(report["ok"])
            issue = next(issue for issue in report["issues"] if issue["code"] == "style-profile-empty-visible-pixels")
            self.assertEqual(issue["job_id"], "button-sheet-01")
            self.assertEqual(issue["asset_id"], "button")
            self.assertEqual(issue["file"], "final/Button/button.png")


if __name__ == "__main__":
    unittest.main()
