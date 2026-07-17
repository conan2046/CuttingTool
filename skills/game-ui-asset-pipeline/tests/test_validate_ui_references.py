from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "validate_ui_references.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_ui_references", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


class ValidateUiReferencesTest(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        references = root / "input" / "test-ui" / "references"
        references.mkdir(parents=True)
        (references / "reference-notes.md").write_text("# notes\n", encoding="utf-8")
        return references

    def test_empty_directory_waits_for_user_references(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            references = self.make_project(Path(temporary_directory))
            result = MODULE.validate_references(references)
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "awaiting-user-references")
            self.assertIn("no-reference-images", {item["code"] for item in result["issues"]})

    def test_valid_canonical_and_supporting_references_are_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            references = self.make_project(Path(temporary_directory))
            Image.new("RGB", (512, 512), (20, 40, 60)).save(references / "canonical-style.png")
            Image.new("RGB", (256, 320), (80, 90, 100)).save(references / "reference-01-material.png")
            result = MODULE.validate_references(references)
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "ready-for-visual-review")
            self.assertEqual(result["canonical_count"], 1)
            self.assertEqual(result["supporting_count"], 1)

    def test_badly_named_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            references = self.make_project(Path(temporary_directory))
            Image.new("RGB", (128, 128), (20, 40, 60)).save(references / "my ref.png")
            result = MODULE.validate_references(references)
            self.assertFalse(result["ok"])
            codes = {item["code"] for item in result["issues"]}
            self.assertIn("invalid-reference-name", codes)

    def test_small_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            references = self.make_project(Path(temporary_directory))
            Image.new("RGB", (128, 128), (20, 40, 60)).save(references / "reference-01-material.png")
            result = MODULE.validate_references(references)
            self.assertFalse(result["ok"])
            self.assertIn("reference-too-small", {item["code"] for item in result["issues"]})

    def test_duplicate_reference_content_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            references = self.make_project(Path(temporary_directory))
            image = Image.new("RGB", (256, 256), (20, 40, 60))
            image.save(references / "reference-01-material.png")
            image.save(references / "reference-02-color.png")
            result = MODULE.validate_references(references)
            self.assertFalse(result["ok"])
            self.assertIn("duplicate-reference-content", {item["code"] for item in result["issues"]})


if __name__ == "__main__":
    unittest.main()
