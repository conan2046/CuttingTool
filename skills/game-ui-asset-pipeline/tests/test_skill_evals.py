from __future__ import annotations

import json
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CATEGORIES = {
    "Panel",
    "Button",
    "Icon_Nav",
    "Icon_Status",
    "Icon_General",
    "Icon_Item",
    "Icon_Equip",
    "Icon_Skill",
    "Icon_Effect",
}


class SkillEvalsTest(unittest.TestCase):
    def test_all_standard_categories_have_one_trigger_eval(self) -> None:
        payload = json.loads((SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
        evals = payload["evals"]
        categories = [case["category"] for case in evals if case.get("kind") == "category-trigger"]
        self.assertEqual(set(categories), EXPECTED_CATEGORIES)
        self.assertEqual(len(categories), len(EXPECTED_CATEGORIES))
        self.assertEqual(len(categories), len(set(categories)))

    def test_trigger_evals_define_expected_skill_and_first_action(self) -> None:
        payload = json.loads((SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
        for case in payload["evals"]:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["prompt"].strip())
                self.assertTrue(case["expected_output"].strip())
                if case.get("kind") == "category-trigger":
                    self.assertEqual(case["expected_skill"], "game-ui-asset-pipeline")
                    self.assertIn(case["category"], case["expected_output"])
                    self.assertTrue(case["expected_first_action"].strip())

    def test_latest_fresh_task_acceptance_passes_all_categories(self) -> None:
        payload = json.loads(
            (SKILL_ROOT / "evals" / "trigger-acceptance-2026-07-16.json").read_text(encoding="utf-8")
        )
        cases = payload["cases"]
        self.assertEqual({case["category"] for case in cases}, EXPECTED_CATEGORIES)
        self.assertEqual(payload["summary"], {"expected": 9, "passed": 9, "failed": 0})
        for case in cases:
            with self.subTest(category=case["category"]):
                self.assertEqual(case["selected_skill"], "game-ui-asset-pipeline")
                self.assertEqual(case["result"], "pass")
                self.assertTrue(case["thread_id"].strip())
                self.assertTrue(case["first_action"].strip())

    def test_p6_orchestration_trigger_defines_one_click_first_action(self) -> None:
        payload = json.loads((SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
        cases = [case for case in payload["evals"] if case.get("kind") == "orchestration-trigger"]
        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertEqual(case["expected_skill"], "game-ui-asset-pipeline")
        self.assertIn("批量请求", case["expected_first_action"])
        self.assertIn("orchestrate_ui_delivery.py", case["expected_output"])
        self.assertIn("awaiting-generation", case["expected_output"])

    def test_first_use_onboarding_requires_project_initialization(self) -> None:
        payload = json.loads((SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
        cases = [case for case in payload["evals"] if case.get("kind") == "first-use-onboarding"]
        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertEqual(case["expected_skill"], "game-ui-asset-pipeline")
        self.assertIn("询问用户输入项目名", case["expected_first_action"])
        self.assertIn("initialize_ui_project.py", case["expected_first_action"])
        self.assertIn("暂停等待用户放图", case["expected_first_action"])
        self.assertIn("validate_ui_references.py", case["expected_output"])
        self.assertIn("全部通过后", case["expected_output"])

    def test_reference_intake_gate_blocks_generation_until_review_passes(self) -> None:
        payload = json.loads((SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
        cases = [case for case in payload["evals"] if case.get("kind") == "reference-intake-gate"]
        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertIn("validate_ui_references.py", case["expected_first_action"])
        self.assertIn("view_image", case["expected_first_action"])
        self.assertIn("失败", case["expected_output"])
        self.assertIn("只有全部通过后", case["expected_output"])

    def test_unity_export_eval_requires_safe_border_and_reports(self) -> None:
        payload = json.loads((SKILL_ROOT / "evals" / "evals.json").read_text(encoding="utf-8"))
        cases = [case for case in payload["evals"] if case.get("kind") == "unity-export"]
        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertEqual(case["expected_skill"], "game-ui-asset-pipeline")
        self.assertIn("Unity版本", case["expected_first_action"])
        self.assertIn("nine_slice_overrides", case["expected_output"])
        self.assertIn("回滚清单", case["expected_output"])


if __name__ == "__main__":
    unittest.main()
