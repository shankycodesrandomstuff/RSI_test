#!/usr/bin/env python3
"""Human-invoked entry point for the local experiment."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rsi.engine import LOG_ROOT, ExperimentConfig, run_experiment
from rsi.schema import PolicyError, load_policy


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline sandboxed RSI prototype")
    parser.add_argument("--baseline", type=Path, default=Path("artifacts/baseline_policy.json"))
    parser.add_argument("--output", default="logs/demo", help="relative path below this project's logs/ directory")
    parser.add_argument("--generations", type=int, default=5)
    parser.add_argument("--candidates", type=int, default=12)
    parser.add_argument("--train-survivors", type=int, default=4)
    parser.add_argument("--min-improvement", type=float, default=0.002)
    parser.add_argument("--seed", type=int, default=20260910)
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parent
    requested = Path(args.output)
    if requested.is_absolute() or ".." in requested.parts:
        parser.error("--output must be a relative path beneath logs/")
    output = (project_root / requested).resolve()
    requested_baseline = Path(args.baseline)
    if requested_baseline.is_absolute() or ".." in requested_baseline.parts:
        parser.error("--baseline must be a relative path beneath artifacts/")
    baseline_path = (project_root / requested_baseline).resolve()
    artifact_root = (project_root / "artifacts").resolve()
    if artifact_root not in baseline_path.parents:
        parser.error("--baseline must remain beneath artifacts/")
    try:
        baseline = load_policy(baseline_path)
        summary = run_experiment(baseline, ExperimentConfig(args.generations, args.candidates,
                                 args.train_survivors, args.min_improvement, args.seed), output)
    except (OSError, ValueError, PolicyError, FileExistsError) as exc:
        print(f"experiment failed safely: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
