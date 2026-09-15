from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from rsi.engine import ExperimentConfig, LOG_ROOT, evaluate_subprocess, run_experiment
from rsi.schema import PolicyError, load_policy, policy_from_dict, safe_child


ROOT = Path(__file__).resolve().parents[1]


class PrototypeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.baseline = load_policy(ROOT / "artifacts" / "baseline_policy.json")

    def tearDown(self) -> None:
        for name in ("_test-run",):
            path = LOG_ROOT / name
            if path.exists():
                shutil.rmtree(path)

    def test_schema_rejects_extra_code_surface(self) -> None:
        data = self.baseline.canonical()
        data["python"] = "import os"
        with self.assertRaises(PolicyError):
            policy_from_dict(data)

    def test_safe_child_rejects_escape(self) -> None:
        with self.assertRaises(PolicyError):
            safe_child(ROOT / "logs", "..", "elsewhere")

    def test_evaluation_is_reproducible(self) -> None:
        first = evaluate_subprocess(self.baseline, "train", LOG_ROOT)
        second = evaluate_subprocess(self.baseline, "train", LOG_ROOT)
        self.assertNotIn("error", first)
        self.assertEqual(first["mean_score"], second["mean_score"])
        self.assertEqual(first["policy_hash"], self.baseline.digest())

    def test_one_generation_logs_all_attempts_and_preserves_best(self) -> None:
        output = LOG_ROOT / "_test-run"
        summary = run_experiment(self.baseline, ExperimentConfig(generations=1, candidates=2,
                                 train_survivors=1, min_improvement=0.99, seed=44), output)
        run = json.loads((output / "run.json").read_text())
        self.assertEqual(len(run["generations"]), 1)
        self.assertEqual(len(run["generations"][0]["candidates"]), 2)
        self.assertEqual(run["generations"][0]["decision"], "retained-incumbent")
        self.assertEqual(summary["best_hash"], self.baseline.digest())
        self.assertTrue((output / "best_policy.json").exists())
        self.assertEqual(run["baseline_metrics"]["validation"]["policy_hash"], self.baseline.digest())


if __name__ == "__main__":
    unittest.main()
