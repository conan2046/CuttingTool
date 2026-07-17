import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


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


PREPARE = load_module("prepare_ui_batch")
RUNNER = load_module("run_ui_pipeline")
NATIVE = load_module("native_alpha")
MATTE = load_module("apply_alpha_matte")


class P5NativeAlphaTest(unittest.TestCase):
    def native_request(self) -> dict:
        return {
            "project_id": "p5-native-alpha-matrix",
            "style_notes": "synthetic native alpha fidelity matrix",
            "generation_method": "synthetic-native-alpha-fixture",
            "categories": [
                {
                    "category": "Icon_Effect",
                    "transparency_mode": "native-alpha-required",
                    "canvas": [256, 256],
                    "grid": [2, 2],
                    "target_size": [96, 96],
                    "outer_margin": 12,
                    "gutter": 12,
                    "safe_padding": 10,
                    "padding": 6,
                    "assets": [
                        {"semantic_name": "Smoke", "description": "wispy smoke"},
                        {"semantic_name": "Glass", "description": "glass shield"},
                        {"semantic_name": "Liquid", "description": "liquid splash"},
                        {"semantic_name": "SoftGlow", "description": "soft glow"},
                    ],
                }
            ],
        }

    def write_layered_sheet(self, run_dir: Path) -> tuple[Path, Path]:
        jobs = json.loads((run_dir / "jobs.json").read_text(encoding="utf-8"))["jobs"]
        job = jobs[0]
        layout = json.loads((run_dir / job["layout_json"]).read_text(encoding="utf-8"))
        rgba = np.zeros((256, 256, 4), dtype=np.uint8)
        colors = ((90, 150, 230), (190, 225, 255), (35, 205, 215), (255, 205, 70))
        yy, xx = np.mgrid[0:256, 0:256]
        for index, slot in enumerate(layout["slots"][:4]):
            safe = slot["safe_box"]
            cx = (safe["left"] + safe["right"]) / 2
            cy = (safe["top"] + safe["bottom"]) / 2
            radius = min(safe["right"] - safe["left"], safe["bottom"] - safe["top"]) * 0.38
            distance = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
            alpha = np.clip((1.0 - distance / radius) * (180 + index * 15), 0, 245).astype(np.uint8)
            if index == 1:
                inner = distance < radius * 0.42
                alpha[inner] = np.maximum(alpha[inner] // 3, 24)
            visible = alpha > 0
            for channel, value in enumerate(colors[index]):
                rgba[:, :, channel][visible] = value
            rgba[:, :, 3] = np.maximum(rgba[:, :, 3], alpha)
        source = run_dir / job["generated_output"]
        Image.fromarray(rgba, mode="RGBA").save(source)
        provenance = run_dir / job["provenance_file"]
        provenance.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "transparency_mode": "native-alpha-required",
                    "alpha_origin": "model-native",
                    "background_removal_applied": False,
                    "generation_method": "synthetic-native-alpha-fixture",
                    "model": "deterministic-test-fixture",
                    "source_output": job["generated_output"],
                    "source_sha256": NATIVE.sha256_file(source),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return source, provenance

    def test_four_effect_classes_preserve_verified_native_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            PREPARE.prepare_batch(self.native_request(), run_dir)
            prompt = (run_dir / "prompts" / "icon-effect-sheet-01.md").read_text(encoding="utf-8")
            self.assertIn("genuine RGBA alpha channel", prompt)
            self.assertNotIn("chroma-key background", prompt)
            self.write_layered_sheet(run_dir)

            result = RUNNER.run_pipeline(run_dir)
            self.assertTrue(result["ok"], result)
            manifest = json.loads((run_dir / "final" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["native_alpha_verified_sheets"], 1)
            self.assertEqual([entry["semantic_name"] for entry in manifest["assets"]], [
                "Smoke", "Glass", "Liquid", "SoftGlow"
            ])
            for entry in manifest["assets"]:
                self.assertEqual(entry["alpha_origin"], "model-native")
                self.assertEqual(entry["transparency_mode"], "native-alpha-required")
                with Image.open(run_dir / entry["output"]) as image:
                    alpha = np.asarray(image.getchannel("A"), dtype=np.uint8)
                self.assertGreater(np.count_nonzero((alpha > 0) & (alpha < 255)), 32)
                self.assertGreaterEqual(np.unique(alpha).size, 8)
            summary = json.loads((run_dir / "qa" / "run-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["generation"]["native_alpha_verified_count"], 1)

    def test_built_in_generation_is_rejected_for_native_alpha_jobs(self) -> None:
        request = self.native_request()
        request["generation_method"] = "built-in-imagegen"
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(ValueError, "cannot prove native alpha"):
                PREPARE.prepare_batch(request, Path(temporary_directory) / "run")

    def test_real_built_in_checkerboard_probe_is_rejected_before_formal_output(self) -> None:
        sample = SKILL_DIR / "tests" / "fixtures" / "built-in-checkerboard-rgb-crop.png"
        self.assertTrue(sample.is_file(), sample)
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            PREPARE.prepare_batch(self.native_request(), run_dir)
            job = json.loads((run_dir / "jobs.json").read_text(encoding="utf-8"))["jobs"][0]
            source = run_dir / job["generated_output"]
            shutil.copy2(sample, source)
            provenance = run_dir / job["provenance_file"]
            provenance.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "transparency_mode": "native-alpha-required",
                        "alpha_origin": "model-native",
                        "background_removal_applied": False,
                        "generation_method": "built-in-imagegen",
                        "model": "gpt-image-2",
                        "source_output": job["generated_output"],
                        "source_sha256": NATIVE.sha256_file(source),
                    }
                ),
                encoding="utf-8",
            )
            result = RUNNER.run_pipeline(run_dir)
            self.assertFalse(result["ok"])
            self.assertFalse((run_dir / "final" / "manifest.json").exists())
            report = json.loads((run_dir / "qa" / "icon-effect-sheet-01-native-alpha.json").read_text(encoding="utf-8"))
            codes = {issue["code"] for issue in report["issues"]}
            self.assertIn("source-has-no-alpha-channel", codes)
            self.assertIn("built-in-imagegen-not-native-alpha", codes)

    def test_background_removed_rgba_cannot_claim_native_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            PREPARE.prepare_batch(self.native_request(), run_dir)
            source, provenance_path = self.write_layered_sheet(run_dir)
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            provenance["background_removal_applied"] = True
            provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
            report = NATIVE.validate_native_alpha_source(
                source, provenance_path, "generated/icon-effect-sheet-01.png"
            )
            self.assertFalse(report["ok"])
            self.assertIn("background-removal-not-native-alpha", {issue["code"] for issue in report["issues"]})

    def test_missing_generation_method_cannot_claim_native_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            PREPARE.prepare_batch(self.native_request(), run_dir)
            source, provenance_path = self.write_layered_sheet(run_dir)
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            provenance["generation_method"] = ""
            provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
            report = NATIVE.validate_native_alpha_source(
                source, provenance_path, "generated/icon-effect-sheet-01.png"
            )
            self.assertFalse(report["ok"])
            self.assertIn("missing-generation-method", {issue["code"] for issue in report["issues"]})


class P5ModelMatteTest(unittest.TestCase):
    def matte_request(self) -> dict:
        return {
            "project_id": "p5-model-matte-matrix",
            "style_notes": "synthetic RGB plus model matte matrix",
            "generation_method": "built-in-imagegen",
            "categories": [
                {
                    "category": "Icon_Effect",
                    "transparency_mode": "model-matte-derived",
                    "canvas": [256, 256],
                    "grid": [2, 2],
                    "target_size": [96, 96],
                    "outer_margin": 12,
                    "gutter": 12,
                    "safe_padding": 10,
                    "padding": 6,
                    "assets": ["Smoke", "Glass", "Liquid", "SoftGlow"],
                }
            ],
        }

    def write_color_and_matte(self, run_dir: Path, matte_color_bias: int = 0) -> tuple[Path, Path]:
        job = json.loads((run_dir / "jobs.json").read_text(encoding="utf-8"))["jobs"][0]
        layout = json.loads((run_dir / job["layout_json"]).read_text(encoding="utf-8"))
        color = np.zeros((256, 256, 3), dtype=np.uint8)
        matte = np.zeros((256, 256, 3), dtype=np.uint8)
        colors = ((90, 150, 230), (190, 225, 255), (35, 205, 215), (255, 205, 70))
        yy, xx = np.mgrid[0:256, 0:256]
        for index, slot in enumerate(layout["slots"][:4]):
            safe = slot["safe_box"]
            cx = (safe["left"] + safe["right"]) / 2
            cy = (safe["top"] + safe["bottom"]) / 2
            radius = min(safe["right"] - safe["left"], safe["bottom"] - safe["top"]) * 0.38
            distance = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
            alpha = np.clip((1.0 - distance / radius) * (180 + index * 15), 0, 245).astype(np.uint8)
            if index == 1:
                inner = distance < radius * 0.42
                alpha[inner] = np.maximum(alpha[inner] // 3, 24)
            for channel, value in enumerate(colors[index]):
                premultiplied = np.rint(value * (alpha.astype(np.float32) / 255.0)).astype(np.uint8)
                color[:, :, channel] = np.maximum(color[:, :, channel], premultiplied)
            matte[:, :, 0] = np.maximum(matte[:, :, 0], alpha)
            matte[:, :, 1] = np.maximum(matte[:, :, 1], alpha)
            matte[:, :, 2] = np.maximum(matte[:, :, 2], np.clip(alpha.astype(int) + matte_color_bias, 0, 255))
        source_path = run_dir / job["generated_output"]
        matte_path = run_dir / job["alpha_matte_output"]
        Image.fromarray(color, mode="RGB").save(source_path)
        Image.fromarray(matte, mode="RGB").save(matte_path)
        return source_path, matte_path

    def test_built_in_color_plus_matte_runs_complete_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            PREPARE.prepare_batch(self.matte_request(), run_dir)
            job = json.loads((run_dir / "jobs.json").read_text(encoding="utf-8"))["jobs"][0]
            color_prompt = (run_dir / job["prompt_file"]).read_text(encoding="utf-8")
            matte_prompt = (run_dir / job["alpha_matte_prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("flat pure black RGB background", color_prompt)
            self.assertIn("Pure white means fully opaque", matte_prompt)
            self.write_color_and_matte(run_dir)

            result = RUNNER.run_pipeline(run_dir)
            self.assertTrue(result["ok"], result)
            manifest = json.loads((run_dir / "final" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["model_matte_verified_sheets"], 1)
            for entry in manifest["assets"]:
                self.assertEqual(entry["alpha_origin"], "gpt-image-2-matte-derived")
                self.assertRegex(entry["alpha_matte_sha256"], r"^[0-9a-f]{64}$")
            report = json.loads((run_dir / "qa" / "icon-effect-sheet-01-alpha-matte.json").read_text(encoding="utf-8"))
            self.assertTrue(report["ok"], report)

    def test_non_grayscale_matte_is_rejected_before_formal_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            PREPARE.prepare_batch(self.matte_request(), run_dir)
            self.write_color_and_matte(run_dir, matte_color_bias=80)
            result = RUNNER.run_pipeline(run_dir)
            self.assertFalse(result["ok"])
            self.assertFalse((run_dir / "final" / "manifest.json").exists())
            report = json.loads((run_dir / "qa" / "icon-effect-sheet-01-alpha-matte.json").read_text(encoding="utf-8"))
            self.assertIn("matte-not-grayscale", {issue["code"] for issue in report["issues"]})

    def test_flat_opaque_matte_is_rejected(self) -> None:
        source = Image.new("RGB", (128, 128), (0, 0, 0))
        matte = Image.new("RGB", (128, 128), (255, 255, 255))
        _output, report = MATTE.apply_alpha_matte(source, matte)
        self.assertFalse(report["ok"])
        codes = {issue["code"] for issue in report["issues"]}
        self.assertIn("matte-border-not-transparent", codes)
        self.assertIn("insufficient-partial-alpha-pixels", codes)

    def test_shifted_matte_is_rejected_as_pixel_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            PREPARE.prepare_batch(self.matte_request(), run_dir)
            source_path, matte_path = self.write_color_and_matte(run_dir)
            with Image.open(matte_path) as opened:
                matte = np.asarray(opened, dtype=np.uint8).copy()
            shifted = np.zeros_like(matte)
            shifted[32:, 32:] = matte[:-32, :-32]
            Image.fromarray(shifted, mode="RGB").save(matte_path)
            with Image.open(source_path) as source, Image.open(matte_path) as matte_image:
                _output, report = MATTE.apply_alpha_matte(source, matte_image)
            self.assertFalse(report["ok"])
            self.assertIn("source-matte-pixel-mismatch", {issue["code"] for issue in report["issues"]})

    def test_matte_size_mismatch_is_rejected_before_export(self) -> None:
        source = Image.new("RGB", (128, 128), (0, 0, 0))
        matte = Image.new("RGB", (64, 64), (0, 0, 0))
        _output, report = MATTE.apply_alpha_matte(source, matte)
        self.assertFalse(report["ok"])
        self.assertTrue(report["matte_resized_to_source"])
        self.assertIn("source-matte-size-mismatch", {issue["code"] for issue in report["issues"]})

    def test_polluted_source_border_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            PREPARE.prepare_batch(self.matte_request(), run_dir)
            source_path, matte_path = self.write_color_and_matte(run_dir)
            with Image.open(source_path) as opened:
                source = np.asarray(opened, dtype=np.uint8).copy()
            source[:8, :, 0] = np.tile(np.arange(source.shape[1], dtype=np.uint8), (8, 1))
            Image.fromarray(source, mode="RGB").save(source_path)
            with Image.open(source_path) as source_image, Image.open(matte_path) as matte_image:
                _output, report = MATTE.apply_alpha_matte(source_image, matte_image)
            self.assertFalse(report["ok"])
            self.assertIn("source-background-not-flat", {issue["code"] for issue in report["issues"]})


if __name__ == "__main__":
    unittest.main()
