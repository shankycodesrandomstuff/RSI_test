"""Promotion loop and the boring parts that keep candidate evaluation boxed in."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .generator import MutationGenerator, Proposal
from .schema import PolicyError, PolicyProgram, safe_child

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_ROOT = (PROJECT_ROOT / "logs").resolve()
EVALUATOR_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class ExperimentConfig:
    generations: int = 5
    candidates: int = 12
    train_survivors: int = 4
    min_improvement: float = 0.002
    seed: int = 20260910

    def validate(self) -> None:
        if not (1 <= self.generations <= 100 and 2 <= self.candidates <= 64):
            raise ValueError("generations must be 1..100 and candidates must be 2..64")
        if not (1 <= self.train_survivors <= self.candidates):
            raise ValueError("train_survivors must be between 1 and candidates")
        if not (0.0 <= self.min_improvement < 1.0):
            raise ValueError("min_improvement must be in [0, 1)")


def _limit_child_resources() -> None:
    """Best-effort POSIX limits. Docker or a VM is still the real boundary for untrusted code."""
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (15, 16))
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    except (ImportError, OSError, ValueError):
        pass


def evaluate_subprocess(policy: PolicyProgram, split: str, output_root: Path) -> dict[str, Any]:
    """Evaluate in a fresh process; the JSON policy never turns into executable source."""
    scratch = safe_child(output_root, "_scratch")
    scratch.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="eval-", dir=scratch) as temp_name:
        temp = Path(temp_name)
        candidate_path = temp / "candidate.json"
        policy.to_json(candidate_path)
        environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONNOUSERSITE": "1", "LC_ALL": "C"}
        command = [sys.executable, "-E", "-s", "-m", "rsi.evaluator", "--policy", str(candidate_path), "--split", split]
        try:
            completed = subprocess.run(
                command, cwd=PROJECT_ROOT, env=environment, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, timeout=EVALUATOR_TIMEOUT_SECONDS,
                preexec_fn=_limit_child_resources if os.name == "posix" else None,
            )
        except subprocess.TimeoutExpired:
            return {"error": f"timeout after {EVALUATOR_TIMEOUT_SECONDS}s", "elapsed_seconds": time.monotonic() - started}
    elapsed = time.monotonic() - started
    if completed.returncode != 0:
        return {"error": f"evaluator exit {completed.returncode}", "stdout": completed.stdout[-1000:],
                "stderr": completed.stderr[-1000:], "elapsed_seconds": elapsed}
    try:
        result = json.loads(completed.stdout)
        if "error" in result or result.get("policy_hash") != policy.digest():
            raise ValueError("malformed or mismatched evaluator result")
        result["elapsed_seconds"] = elapsed
        return result
    except (json.JSONDecodeError, ValueError) as exc:
        return {"error": f"invalid evaluator output: {exc}", "stdout": completed.stdout[-1000:], "elapsed_seconds": elapsed}


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _metric(result: dict[str, Any], key: str) -> float:
    return float(result[key]) if "error" not in result else float("-inf")


def _proposal_log(proposal: Proposal, train: dict[str, Any], validation: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"policy": proposal.policy.canonical(), "policy_hash": proposal.policy.digest(),
            "source": proposal.source, "changed": {key: list(value) for key, value in proposal.changed.items()},
            "train": train, "validation": validation}


def run_experiment(baseline: PolicyProgram, config: ExperimentConfig, output_root: Path) -> dict[str, Any]:
    config.validate()
    output_root = output_root.resolve()
    if output_root != LOG_ROOT and LOG_ROOT not in output_root.parents:
        raise PolicyError(f"output must remain under {LOG_ROOT}")
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty run directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=False)
    safe_child(output_root, "_scratch").mkdir()
    try:
        baseline.to_json(safe_child(output_root, "baseline.json"))
        incumbent = baseline
        incumbent_scores = {split: evaluate_subprocess(incumbent, split, output_root)
                            for split in ("train", "validation", "audit")}
        run: dict[str, Any] = {
            "format": "sandboxed-rsi-run-v1", "config": asdict(config), "baseline": incumbent.canonical(),
            "baseline_hash": incumbent.digest(), "baseline_metrics": deepcopy(incumbent_scores), "generations": [],
        }
        generator = MutationGenerator(config.seed)
        for generation in range(1, config.generations + 1):
            parent = incumbent
            proposals = generator.propose(parent, generation, config.candidates)
            candidate_dir = safe_child(output_root, "candidates", f"generation-{generation:03d}")
            candidate_dir.mkdir(parents=True)
            records: list[dict[str, Any]] = []
            for index, proposal in enumerate(proposals):
                proposal.policy.to_json(safe_child(candidate_dir, f"candidate-{index:03d}.json"))
                train = evaluate_subprocess(proposal.policy, "train", output_root)
                records.append(_proposal_log(proposal, train))
            survivors = sorted(range(len(proposals)), key=lambda i: _metric(records[i]["train"], "mean_score"), reverse=True)[:config.train_survivors]
            for index in survivors:
                records[index]["validation"] = evaluate_subprocess(proposals[index].policy, "validation", output_root)
            promotable = [i for i in survivors if "error" not in records[i]["validation"]]
            winner = max(promotable, key=lambda i: _metric(records[i]["validation"], "mean_score")) if promotable else None
            old_validation = _metric(incumbent_scores["validation"], "mean_score")
            promoted = winner is not None and _metric(records[winner]["validation"], "mean_score") >= old_validation + config.min_improvement
            if promoted:
                incumbent = proposals[winner].policy
                incumbent_scores["train"] = records[winner]["train"]
                incumbent_scores["validation"] = records[winner]["validation"]
                decision = "promoted"
            else:
                decision = "retained-incumbent"
            incumbent_scores["audit"] = evaluate_subprocess(incumbent, "audit", output_root)
            generation_log = {
                "generation": generation, "parent_hash": parent.digest(), "parent_validation": old_validation,
                "survivor_indices": survivors, "winner_index": winner, "decision": decision,
                "incumbent_hash_after": incumbent.digest(), "incumbent_metrics_after": deepcopy(incumbent_scores),
                "candidates": records,
            }
            _write_json(safe_child(candidate_dir, "generation.json"), generation_log)
            run["generations"].append(generation_log)
            _write_json(safe_child(output_root, "run.json"), run)
        incumbent.to_json(safe_child(output_root, "best_policy.json"))
        summary = {"best_policy": incumbent.canonical(), "best_hash": incumbent.digest(),
                   "metrics": deepcopy(incumbent_scores),
                   "promotions": sum(1 for item in run["generations"] if item["decision"] == "promoted")}
        _write_json(safe_child(output_root, "summary.json"), summary)
        return summary
    finally:
        scratch = safe_child(output_root, "_scratch")
        if scratch.exists():
            shutil.rmtree(scratch)
