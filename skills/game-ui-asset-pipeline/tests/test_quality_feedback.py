import importlib.util
import sys
import unittest
from pathlib import Path


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


QUALITY = load_module("quality_feedback")


class QualityFeedbackTest(unittest.TestCase):
    def test_hard_blocker_scores_candidate_but_never_unblocks_it(self) -> None:
        jobs = [{"id": "button-sheet-01"}]
        assets = [{"id": "02_Button_Confirm_Normal_001"}]
        report = {
            "issues": [
                {
                    "severity": "fail",
                    "code": "canvas-edge-contact",
                    "job_id": "button-sheet-01",
                    "asset_id": "02_Button_Confirm_Normal_001",
                }
            ]
        }
        quality = QUALITY.evaluate_quality(report, jobs, assets)
        self.assertEqual(quality["score"], 66)
        self.assertEqual(quality["status"], "blocked")
        self.assertEqual(quality["hard_blocker_count"], 1)
        self.assertEqual(quality["jobs"][0]["status"], "blocked")
        self.assertEqual(quality["assets"][0]["score"], 66)
        self.assertIn("forbids formal delivery", quality["scoring_policy"])

    def test_primary_issue_selects_one_highest_priority_correction(self) -> None:
        issue = QUALITY.primary_issue(
            [
                {"severity": "warning", "code": "detached-components"},
                {"severity": "fail", "code": "visible-chroma-spill"},
                {"severity": "fail", "code": "count-mismatch"},
            ]
        )
        self.assertIsNotNone(issue)
        self.assertEqual(issue["code"], "count-mismatch")
        self.assertEqual(issue["retry_target"], "production-sheet")
        self.assertIn("exactly", issue["correction_instruction"])

    def test_valid_candidate_scores_one_hundred(self) -> None:
        quality = QUALITY.evaluate_quality({"issues": []}, [{"id": "panel-sheet-01"}])
        self.assertEqual(quality["score"], 100)
        self.assertEqual(quality["status"], "excellent")
        self.assertEqual(quality["hard_blocker_count"], 0)

    def test_style_drift_produces_one_focused_sheet_correction(self) -> None:
        issue = QUALITY.primary_issue(
            [{"severity": "fail", "code": "cross-sheet-style-drift", "job_id": "button-sheet-01"}]
        )
        self.assertEqual(issue["quality_dimension"], "style_consistency")
        self.assertEqual(issue["retry_target"], "production-sheet")
        self.assertIn("canonical palette", issue["correction_instruction"])


if __name__ == "__main__":
    unittest.main()
