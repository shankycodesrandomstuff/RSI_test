#!/usr/bin/env python3
"""Human-invoked launcher for the source-level experiment."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from source_rsi.engine import ROOT, SourceExperimentConfig, run_source_experiment


def main() -> int:
    parser = argparse.ArgumentParser(description="Sandboxed source-level recursive improvement experiment")
    parser.add_argument("--baseline", default="source_rsi/artifacts/baseline_optimizer.py")
    parser.add_argument("--output", default="source_rsi/source_runs/verified-source-demo")
    parser.add_argument("--generations", type=int, default=4)
    parser.add_argument("--candidates", type=int, default=6)
    parser.add_argument("--train-survivors", type=int, default=2)
    parser.add_argument("--min-improvement", type=float, default=0.002)
    parser.add_argument("--seed", type=int, default=20260910)
    args = parser.parse_args()
    project = Path(__file__).resolve().parent
    baseline, output = Path(args.baseline), Path(args.output)
    if baseline.is_absolute() or output.is_absolute() or ".." in baseline.parts or ".." in output.parts:
        parser.error("baseline and output must be relative paths inside this project")
    try:
        summary = run_source_experiment(project / baseline, SourceExperimentConfig(args.generations, args.candidates,
                                        args.train_survivors, args.min_improvement, args.seed), project / output)
    except (OSError, ValueError, FileExistsError) as exc:
        print(f"source experiment failed safely: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
