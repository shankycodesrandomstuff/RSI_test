"""Standalone candidate evaluator used only inside a short-lived subprocess."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from .benchmark import FUNCTIONS, split_seeds
from .policy import optimize
from .schema import PolicyError, load_policy


def evaluate(policy_path: Path, split: str) -> dict:
    policy = load_policy(policy_path)
    rows = []
    for function_name, objective in FUNCTIONS:
        for seed in split_seeds(split):
            cost, calls = optimize(policy, objective, seed)
            rows.append({"function": function_name, "seed": seed, "best_cost": cost, "calls": calls,
                         "score": 1.0 / (1.0 + cost)})
    return {
        "policy_hash": policy.digest(), "split": split, "runs": len(rows),
        "mean_score": statistics.fmean(row["score"] for row in rows),
        "mean_cost": statistics.fmean(row["best_cost"] for row in rows), "details": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate one validated JSON policy.")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--split", required=True, choices=("train", "validation", "audit"))
    args = parser.parse_args()
    policy_path = Path(args.policy).resolve()
    # The parent copies policies to a private temp directory; do not accept links or paths outside it.
    if policy_path.is_symlink() or policy_path.name != "candidate.json":
        print(json.dumps({"error": "invalid evaluator candidate path"}))
        return 2
    try:
        print(json.dumps(evaluate(policy_path, args.split), sort_keys=True))
        return 0
    except (PolicyError, ValueError, ArithmeticError) as exc:
        print(json.dumps({"error": f"evaluation rejected: {exc}"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
