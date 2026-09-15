"""Source-parent → synthesized child → independent evaluator → promotion loop."""
from __future__ import annotations

import copy
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .evaluator import evaluate_source
from .templates import SourceMutationAI, SourceProposal, source_hash
from .trusted.candidate_validation import CandidateError, load_candidate


ROOT = Path(__file__).resolve().parent
RUN_ROOT = (ROOT / "source_runs").resolve()


@dataclass(frozen=True)
class SourceExperimentConfig:
    generations: int = 4
    candidates: int = 6
    train_survivors: int = 2
    min_improvement: float = 0.002
    seed: int = 20260910

    def validate(self) -> None:
        if not 1 <= self.generations <= 30 or not 3 <= self.candidates <= 24:
            raise ValueError("generations must be 1..30 and candidates must be 3..24")
        if not 1 <= self.train_survivors <= self.candidates:
            raise ValueError("train_survivors must be in 1..candidates")
        if not 0 <= self.min_improvement < 1:
            raise ValueError("min_improvement must be in [0, 1)")


def _safe_child(root: Path, *parts: str) -> Path:
    root, result = root.resolve(), root.joinpath(*parts).resolve()
    if result == root or root not in result.parents:
        raise ValueError("attempted write outside the designated source experiment directory")
    return result


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _score(result: dict[str, Any]) -> float:
    return float(result["mean_score"]) if "error" not in result else float("-inf")


def _record(proposal: SourceProposal, train: dict[str, Any], validation: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "parent_hash": proposal.parent_hash, "child_hash": proposal.child_hash,
        "modification_kind": proposal.kind, "algorithm_changed": proposal.kind == "algorithmic-source-rewrite",
        "changes": {key: list(value) for key, value in proposal.changes.items()},
        "exact_unified_diff": proposal.diff, "train": train, "validation": validation,
    }


def run_source_experiment(baseline_path: Path, config: SourceExperimentConfig, output: Path) -> dict[str, Any]:
    """Run a source-level RSI experiment. All parent-side writes stay under output."""
    config.validate()
    output = output.resolve()
    if output == RUN_ROOT or RUN_ROOT not in output.parents:
        raise ValueError(f"output must be a new directory below {RUN_ROOT}")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty run directory: {output}")
    baseline_path = baseline_path.resolve()
    artifact_root = (ROOT / "artifacts").resolve()
    if artifact_root not in baseline_path.parents:
        raise ValueError("baseline source must remain under source_rsi/artifacts")
    baseline_source = baseline_path.read_text(encoding="utf-8")
    load_candidate(baseline_source)  # validate before creating any candidate process
    output.mkdir(parents=True, exist_ok=False)
    scratch = _safe_child(output, "_scratch")
    scratch.mkdir()
    try:
        _safe_child(output, "baseline_optimizer.py").write_text(baseline_source, encoding="utf-8")
        parent_source = baseline_source
        parent_hash = source_hash(parent_source)
        baseline_file = _safe_child(output, "baseline_optimizer.py")
        incumbent_metrics = {split: evaluate_source(baseline_file, split, scratch) for split in ("train", "validation", "audit")}
        run: dict[str, Any] = {
            "format": "source-rsi-run-v1", "config": asdict(config), "baseline_hash": parent_hash,
            "baseline_metrics": copy.deepcopy(incumbent_metrics), "generations": [],
        }
        synthesizer = SourceMutationAI(config.seed)
        baseline_validation = _score(incumbent_metrics["validation"])
        for generation in range(1, config.generations + 1):
            proposals = synthesizer.propose(parent_source, generation, config.candidates)
            generation_dir = _safe_child(output, "candidates", f"generation-{generation:03d}")
            generation_dir.mkdir(parents=True)
            records: list[dict[str, Any]] = []
            for index, proposal in enumerate(proposals):
                source_file = _safe_child(generation_dir, f"candidate-{index:03d}.py")
                source_file.write_text(proposal.source, encoding="utf-8")
                _safe_child(generation_dir, f"candidate-{index:03d}.diff").write_text(proposal.diff + "\n", encoding="utf-8")
                records.append(_record(proposal, evaluate_source(source_file, "train", scratch)))
            survivors = sorted(range(len(records)), key=lambda i: _score(records[i]["train"]), reverse=True)[:config.train_survivors]
            for index in survivors:
                source_file = _safe_child(generation_dir, f"candidate-{index:03d}.py")
                records[index]["validation"] = evaluate_source(source_file, "validation", scratch)
            valid = [index for index in survivors if "error" not in records[index]["validation"]]
            winner = max(valid, key=lambda i: _score(records[i]["validation"])) if valid else None
            parent_validation = _score(incumbent_metrics["validation"])
            promoted = winner is not None and _score(records[winner]["validation"]) >= parent_validation + config.min_improvement
            if promoted:
                parent_source = proposals[winner].source
                parent_hash = proposals[winner].child_hash
                incumbent_metrics["train"] = records[winner]["train"]
                incumbent_metrics["validation"] = records[winner]["validation"]
                decision = "promoted"
            else:
                decision = "retained-parent"
            current_file = _safe_child(output, "_scratch", "current_parent.py")
            current_file.write_text(parent_source, encoding="utf-8")
            incumbent_metrics["audit"] = evaluate_source(current_file, "audit", scratch)
            entry = {
                "generation": generation, "parent_hash": proposals[0].parent_hash, "parent_validation_score": parent_validation,
                "winner_index": winner, "decision": decision, "promoted": promoted, "child_hash_if_promoted": parent_hash if promoted else None,
                "incumbent_hash_after": parent_hash, "cumulative_validation_improvement": _score(incumbent_metrics["validation"]) - baseline_validation,
                "incumbent_metrics_after": copy.deepcopy(incumbent_metrics), "survivor_indices": survivors, "candidates": records,
            }
            _write_json(_safe_child(generation_dir, "generation.json"), entry)
            run["generations"].append(entry)
            _write_json(_safe_child(output, "run.json"), run)
        _safe_child(output, "best_optimizer.py").write_text(parent_source, encoding="utf-8")
        summary = {
            "best_hash": parent_hash, "best_source": "best_optimizer.py", "metrics": copy.deepcopy(incumbent_metrics),
            "promotions": sum(item["promoted"] for item in run["generations"]),
            "algorithmic_promotions": sum(item["promoted"] and item["candidates"][item["winner_index"]]["algorithm_changed"] for item in run["generations"] if item["winner_index"] is not None),
            "cumulative_validation_improvement": _score(incumbent_metrics["validation"]) - baseline_validation,
        }
        _write_json(_safe_child(output, "summary.json"), summary)
        return summary
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)
