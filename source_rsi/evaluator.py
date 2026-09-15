"""Parent-side evaluator. Candidate scores are not a trusted input, because obviously."""
from __future__ import annotations

import math
import statistics
from pathlib import Path
from typing import Any

from .sandbox import SandboxError, run_candidate
from .templates import source_hash
from .trusted.benchmark import BUDGET, DIMENSION, FUNCTIONS, tasks


def evaluate_source(source_path: Path, split: str, scratch_root: Path) -> dict[str, Any]:
    task_list = tasks(split)
    try:
        worker_result = run_candidate(source_path, task_list, scratch_root)
        traces = worker_result.get("traces")
        if not isinstance(traces, list) or len(traces) != len(task_list):
            raise ValueError("candidate returned wrong number of traces")
        rows = []
        for expected, trace in zip(task_list, traces, strict=True):
            name, seed = expected
            if not isinstance(trace, dict) or (trace.get("function"), trace.get("seed")) != expected:
                raise ValueError("candidate trace task mismatch")
            points = trace.get("points")
            if not isinstance(points, list) or len(points) != BUDGET:
                raise ValueError("candidate trace has wrong budget")
            costs = []
            for point in points:
                if not isinstance(point, list) or len(point) != DIMENSION or any(type(value) not in (int, float) or not math.isfinite(value) or not -5.0 <= value <= 5.0 for value in point):
                    raise ValueError("candidate emitted an invalid point")
                costs.append(FUNCTIONS[name](point))
            best = min(costs)
            rows.append({"function": name, "seed": seed, "best_cost": best, "calls": len(costs), "score": 1 / (1 + best)})
        return {"source_hash": source_hash(source_path.read_text(encoding="utf-8")), "split": split,
                "algorithm_claim": worker_result.get("algorithm"), "runs": len(rows),
                "mean_score": statistics.fmean(row["score"] for row in rows),
                "mean_cost": statistics.fmean(row["best_cost"] for row in rows), "details": rows,
                "sandbox_elapsed_seconds": worker_result["sandbox_elapsed_seconds"]}
    except (SandboxError, OSError, ValueError, ArithmeticError) as exc:
        return {"error": str(exc), "split": split}
