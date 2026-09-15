from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from source_rsi.engine import RUN_ROOT, SourceExperimentConfig, run_source_experiment
from source_rsi.evaluator import evaluate_source
from source_rsi.templates import SourceMutationAI
from source_rsi.trusted.candidate_validation import CandidateError, load_candidate


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "source_rsi" / "artifacts" / "baseline_optimizer.py"


class SourceRsiTests(unittest.TestCase):
    def tearDown(self) -> None:
        path = RUN_ROOT / "_test-source-run"
        if path.exists():
            shutil.rmtree(path)

    def test_rejects_importing_candidate_before_execution(self) -> None:
        source = BASELINE.read_text(encoding="utf-8").replace("POPULATION = 4", "import os\nPOPULATION = 4")
        with self.assertRaises(CandidateError):
            load_candidate(source)

    def test_synthesizer_emits_an_algorithm_body_rewrite(self) -> None:
        source = BASELINE.read_text(encoding="utf-8")
        proposals = SourceMutationAI(3).propose(source, generation=1, count=3)
        algorithmic = next(item for item in proposals if item.kind == "algorithmic-source-rewrite")
        self.assertIn("def propose", algorithmic.diff)
        self.assertNotEqual(algorithmic.parent_hash, algorithmic.child_hash)

    def test_namespace_evaluation_returns_independently_scored_result(self) -> None:
        probe = RUN_ROOT / "_test-source-run"
        (probe / "_scratch").mkdir(parents=True)
        source = probe / "candidate.py"
        source.write_text(BASELINE.read_text(encoding="utf-8"), encoding="utf-8")
        result = evaluate_source(source, "train", probe / "_scratch")
        self.assertNotIn("error", result)
        self.assertEqual(result["runs"], 12)
        self.assertEqual(result["details"][0]["calls"], 240)

    def test_promoted_child_becomes_later_parent(self) -> None:
        output = RUN_ROOT / "_test-source-run"
        run_source_experiment(BASELINE, SourceExperimentConfig(generations=2, candidates=3,
                              train_survivors=1, min_improvement=0.002, seed=20260910), output)
        data = json.loads((output / "run.json").read_text())
        self.assertEqual(data["generations"][1]["parent_hash"], data["generations"][0]["incumbent_hash_after"])


if __name__ == "__main__":
    unittest.main()
