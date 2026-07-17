from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "initialize_ui_project.py"


class InitializeUiProjectTest(unittest.TestCase):
    def run_initializer(self, root: Path, name: str) -> dict[str, object]:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--workspace-root",
                str(root),
                "--project-name",
                name,
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return json.loads(result.stdout)

    def test_creates_reference_notes_under_normalized_project(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            payload = self.run_initializer(root, "Xianxia Bag UI")
            notes = root / "input" / "xianxia-bag-ui" / "references" / "reference-notes.md"
            self.assertTrue(payload["created"])
            self.assertEqual(payload["project_id"], "xianxia-bag-ui")
            self.assertTrue(notes.is_file())
            text = notes.read_text(encoding="utf-8")
            self.assertIn("canonical-style.png", text)
            self.assertIn("reference-01-material.png", text)
            self.assertIn("<!-- 填写说明：", text)
            self.assertIn("填写示例：", text)
            self.assertIn("已放好", text)

    def test_reuses_existing_notes_without_overwriting_user_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = self.run_initializer(root, "xianxia-ui")
            notes = Path(str(first["reference_notes"]))
            notes.write_text("用户已填写的内容\n", encoding="utf-8")
            second = self.run_initializer(root, "xianxia-ui")
            self.assertFalse(second["created"])
            self.assertEqual(notes.read_text(encoding="utf-8"), "用户已填写的内容\n")

    def test_rejects_project_name_without_usable_project_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--workspace-root",
                    temporary_directory,
                    "--project-name",
                    "修仙背包",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("English letter or digit", result.stderr)


if __name__ == "__main__":
    unittest.main()
