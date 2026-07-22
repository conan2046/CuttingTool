from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


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


PREPARE = load_module("prepare_ui_run")


class GenerationOptimizationTest(unittest.TestCase):
    def test_status_prompt_prevents_green_reflection_on_green_chroma(self) -> None:
        prompt = PREPARE.build_prompt(
            "Icon_Status",
            [PREPARE.AssetRequest("Attack"), PREPARE.AssetRequest("Defense")],
            2048,
            2048,
            4,
            4,
            "#00FF00",
            "dark xianxia UI",
            False,
        )

        self.assertIn("opaque dark-navy", prompt)
        self.assertIn("silver-white isolation rim", prompt)
        self.assertIn("No green, cyan-green", prompt)

    def test_non_status_prompt_does_not_force_status_backing(self) -> None:
        prompt = PREPARE.build_prompt(
            "Icon_Equip",
            [PREPARE.AssetRequest("Sword")],
            2048,
            2048,
            4,
            4,
            "#00FF00",
            "dark xianxia UI",
            False,
        )

        self.assertNotIn("Status-icon isolation contract", prompt)


if __name__ == "__main__":
    unittest.main()
