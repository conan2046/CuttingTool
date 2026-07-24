from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SKILL_DIR / "scripts" / "reflow_source_sheet.py"
SPEC = importlib.util.spec_from_file_location("reflow_source_sheet", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {SCRIPT_PATH}")
REFLOW = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = REFLOW
SPEC.loader.exec_module(REFLOW)


class SourceReflowTest(unittest.TestCase):
    def test_reflows_approved_candidates_without_upscaling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = np.zeros((80, 120, 3), dtype=np.uint8)
            source[:, :] = (0, 255, 0)
            source[10:40, 8:28] = (220, 30, 30)
            source[40:70, 82:112] = (30, 30, 220)
            source_path = root / "source.png"
            Image.fromarray(source, mode="RGB").save(source_path)
            layout = {
                "layout": {"width": 200, "height": 100},
                "slots": [
                    {"index": 1, "safe_box": {"left": 10, "top": 10, "right": 90, "bottom": 90}},
                    {"index": 2, "safe_box": {"left": 110, "top": 10, "right": 190, "bottom": 90}},
                ],
            }
            corrections = {
                "approved": True,
                "classification": "flat-background-sheet",
                "background": {
                    "color": "#00FF00",
                    "transparent_threshold": 12,
                    "opaque_threshold": 96,
                },
                "assets": [
                    {"source_index": 1, "enabled": True, "bbox": [8, 10, 28, 40]},
                    {"source_index": 2, "enabled": True, "bbox": [82, 40, 112, 70]},
                ],
            }
            layout_path = root / "layout.json"
            corrections_path = root / "corrections.json"
            layout_path.write_text(json.dumps(layout), encoding="utf-8")
            corrections_path.write_text(json.dumps(corrections), encoding="utf-8")
            output_path = root / "output.png"

            result = REFLOW.reflow_source(source_path, layout_path, corrections_path, output_path)

            self.assertTrue(result["ok"])
            self.assertEqual(result["canvas"], [200, 100])
            self.assertEqual([item["slot_index"] for item in result["placements"]], [1, 2])
            self.assertEqual([item["scale"] for item in result["placements"]], [1.0, 1.0])
            output = np.asarray(Image.open(output_path).convert("RGB"))
            self.assertGreater(int(np.count_nonzero(output[:, :100, 0] > 100)), 0)
            self.assertGreater(int(np.count_nonzero(output[:, 100:, 2] > 100)), 0)


if __name__ == "__main__":
    unittest.main()
