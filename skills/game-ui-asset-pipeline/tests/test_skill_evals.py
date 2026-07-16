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


if __name__ == "__main__":
    unittest.main()
