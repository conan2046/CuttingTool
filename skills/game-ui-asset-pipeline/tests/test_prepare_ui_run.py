import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "prepare_ui_run.py"


class PrepareUiRunTest(unittest.TestCase):
    def test_prepares_button_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--project-id",
                    "Dark Fantasy UI",
                    "--category",
                    "Button",
                    "--asset",
                    "Confirm|Normal|primary action",
                    "--asset",
                    "Confirm|Pressed|pressed state",
                    "--asset",
                    "Confirm|Disabled|disabled state",
                    "--grid",
                    "3x1",
                    "--output-dir",
                    str(run_dir),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            request = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
            jobs = json.loads((run_dir / "jobs.json").read_text(encoding="utf-8"))
            prompt = (run_dir / "prompts" / "button-sheet-01.md").read_text(encoding="utf-8")
            self.assertEqual(request["project_id"], "dark-fantasy-ui")
            self.assertEqual(len(request["assets"]), 3)
            self.assertEqual(request["schema_version"], 2)
            self.assertEqual(request["expected_count"], 3)
            self.assertEqual(jobs["schema_version"], 2)
            self.assertEqual(jobs["jobs"][0]["expected_count"], 3)
            self.assertEqual(
                jobs["jobs"][0]["layout_json"],
                "references/layout-guides/button-sheet-01.json",
            )
            self.assertIn("Exact asset count: 3", prompt)
            guide = run_dir / "references" / "layout-guides" / "button-sheet-01.png"
            with Image.open(guide) as image:
                self.assertEqual(image.size, (2048, 2048))

    def test_rejects_count_over_grid_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            command = [
                sys.executable,
                str(SCRIPT),
                "--project-id",
                "overflow",
                "--category",
                "Icon_Item",
                "--grid",
                "1x1",
                "--asset",
                "Potion",
                "--asset",
                "Scroll",
                "--output-dir",
                str(Path(temporary_directory) / "run"),
            ]
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exceeds grid capacity", result.stderr)

    def test_panel_prompt_forbids_all_four_mid_edge_decorations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            run_dir = Path(temporary_directory) / "run"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--project-id",
                    "nine-slice-panel",
                    "--category",
                    "Panel",
                    "--asset",
                    "Main|Default|clean stretchable panel",
                    "--output-dir",
                    str(run_dir),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            prompt = (run_dir / "prompts" / "panel-sheet-01.md").read_text(encoding="utf-8")
            self.assertIn("middle 60% of the top and bottom borders", prompt)
            self.assertIn("middle 60% of the left and right borders", prompt)
            self.assertIn("Never place a star, diamond, jewel", prompt)


if __name__ == "__main__":
    unittest.main()
