import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_DIR / "scripts"
SAMPLES_DIR = SKILL_DIR.parents[1] / "samples" / "unknown-sheet"
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


DIAGNOSE = load_module("diagnose_ui_sheet")
APPLY = load_module("apply_bbox_corrections")


class UnknownSheetWorkflowTest(unittest.TestCase):
    def alpha_sheet(self) -> Image.Image:
        path = SAMPLES_DIR / "alpha-sheet.png"
        if path.is_file():
            with Image.open(path) as image:
                return image.convert("RGBA")
        image = Image.new("RGBA", (160, 96), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((16, 20, 55, 59), fill=(190, 40, 30, 255))
        draw.rectangle((96, 18, 139, 61), fill=(30, 80, 220, 255))
        return image

    def flat_sheet(self) -> Image.Image:
        image = Image.new("RGB", (160, 96), "#00FF00")
        draw = ImageDraw.Draw(image)
        draw.ellipse((16, 20, 55, 59), fill=(190, 40, 30))
        draw.rectangle((96, 18, 139, 61), fill=(30, 80, 220))
        return image

    def checkerboard_sheet(self) -> Image.Image:
        path = SAMPLES_DIR / "checkerboard-presentation.png"
        if path.is_file():
            with Image.open(path) as image:
                return image.convert("RGB")
        image = Image.new("RGB", (160, 96), "#D0D0D0")
        draw = ImageDraw.Draw(image)
        for y in range(0, image.height, 8):
            for x in range(0, image.width, 8):
                if (x // 8 + y // 8) % 2:
                    draw.rectangle((x, y, x + 7, y + 7), fill="#F0F0F0")
        draw.ellipse((16, 20, 55, 59), fill=(190, 40, 30))
        draw.rectangle((96, 18, 139, 61), fill=(30, 80, 220))
        return image

    def approve(self, corrections: dict) -> dict:
        corrections["approved"] = True
        for index, asset in enumerate(corrections["assets"], start=1):
            asset["semantic_name"] = f"Detected{index}"
        return corrections

    def test_alpha_sheet_diagnosis_and_correction_export(self) -> None:
        diagnosis, corrections, source = DIAGNOSE.diagnose_sheet(
            self.alpha_sheet(), "alpha.png", "Icon_Item", minimum_component_pixels=20
        )
        self.assertEqual(diagnosis["classification"], "alpha-sheet")
        self.assertEqual(diagnosis["candidate_count"], 2)
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ValueError):
                APPLY.apply_corrections(
                    source,
                    corrections,
                    Path(temporary_directory) / "unapproved",
                    "alpha-test",
                    "generated/alpha.png",
                )
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            result = APPLY.apply_corrections(
                source, self.approve(corrections), run_dir, "alpha-test", "generated/alpha.png"
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["exported"], 2)
            self.assertTrue((run_dir / "qa" / "contact-sheet.png").is_file())

    def test_flat_background_diagnosis_and_correction_export(self) -> None:
        diagnosis, corrections, source = DIAGNOSE.diagnose_sheet(
            self.flat_sheet(), "flat.png", "Icon_Item", minimum_component_pixels=20
        )
        self.assertEqual(diagnosis["classification"], "flat-background-sheet")
        self.assertEqual(corrections["background"]["color"], "#00FF00")
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = APPLY.apply_corrections(
                source,
                self.approve(corrections),
                Path(temporary_directory) / "run",
                "flat-test",
                "generated/flat.png",
            )
            self.assertTrue(result["ok"], result)

    def test_checkerboard_is_detected_and_export_is_blocked(self) -> None:
        diagnosis, corrections, source = DIAGNOSE.diagnose_sheet(
            self.checkerboard_sheet(), "checker.png", "Icon_Item", minimum_component_pixels=20
        )
        self.assertEqual(diagnosis["classification"], "checkerboard-presentation")
        self.assertEqual(diagnosis["status"], "manual-review-required")
        self.assertIn("fake-checkerboard-background", {issue["code"] for issue in diagnosis["issues"]})
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ValueError):
                APPLY.apply_corrections(
                    source,
                    self.approve(corrections),
                    Path(temporary_directory) / "run",
                    "checker-test",
                    "generated/checker.png",
                )

    def test_opaque_gradient_is_unresolved(self) -> None:
        x = np.linspace(0, 255, 160, dtype=np.uint8)
        rgb = np.zeros((96, 160, 3), dtype=np.uint8)
        rgb[:, :, 0] = x
        rgb[:, :, 1] = np.flip(x)
        rgb[:, :, 2] = 80
        diagnosis, _, _ = DIAGNOSE.diagnose_sheet(
            Image.fromarray(rgb, mode="RGB"), "gradient.png", "Icon_General", minimum_component_pixels=20
        )
        self.assertEqual(diagnosis["classification"], "opaque-mixed-image")
        self.assertEqual(diagnosis["status"], "manual-review-required")

    def test_overlapping_manual_bboxes_fail_qa(self) -> None:
        _, corrections, source = DIAGNOSE.diagnose_sheet(
            self.alpha_sheet(), "alpha.png", "Icon_Item", minimum_component_pixels=20
        )
        corrections = self.approve(corrections)
        corrections["assets"][1]["bbox"] = list(corrections["assets"][0]["bbox"])
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = APPLY.apply_corrections(
                source,
                corrections,
                Path(temporary_directory) / "run",
                "overlap-test",
                "generated/alpha.png",
            )
            self.assertFalse(result["ok"])
            self.assertGreater(result["fail"], 0)

    def test_retained_failure_sample_cannot_pass_without_correction(self) -> None:
        sample_path = SAMPLES_DIR / "failure-overlap-crop-residue.png"
        if sample_path.is_file():
            with Image.open(sample_path) as image:
                failure_source = image.convert("RGB")
        else:
            failure_source = Image.new("RGB", (160, 96), "#00FF00")
            draw = ImageDraw.Draw(failure_source)
            draw.rectangle((0, 18, 45, 65), fill=(190, 40, 30))
            draw.rectangle((82, 18, 150, 64), fill=(30, 80, 220))
            draw.rectangle((70, 80, 90, 95), fill=(0, 238, 20))
        diagnosis, corrections, source = DIAGNOSE.diagnose_sheet(
            failure_source, "failure.png", "Icon_Item", minimum_component_pixels=20
        )
        self.assertGreater(diagnosis["warning_count"], 0)
        self.assertIn("candidate-touches-canvas", {issue["code"] for issue in diagnosis["issues"]})
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = APPLY.apply_corrections(
                source,
                self.approve(corrections),
                Path(temporary_directory) / "run",
                "failure-test",
                "generated/failure.png",
            )
            self.assertFalse(result["ok"])
            self.assertIn("1", result["manual_action_required"])

    def test_diagnose_cli_rejects_corrupt_image(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            corrupt = root / "corrupt.png"
            corrupt.write_bytes(b"not a png")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "diagnose_ui_sheet.py"),
                    "--input",
                    str(corrupt),
                    "--category",
                    "Icon_Item",
                    "--json-out",
                    str(root / "diagnosis.json"),
                    "--corrections-out",
                    str(root / "corrections.json"),
                    "--preview-out",
                    str(root / "preview.png"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "diagnosis.json").exists())


if __name__ == "__main__":
    unittest.main()
