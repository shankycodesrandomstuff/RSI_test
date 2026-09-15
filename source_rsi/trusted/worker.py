"""Run the candidate and return point traces. Scores stay outside the sandbox."""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark import BUDGET, DIMENSION, DOMAIN, FUNCTIONS
from candidate_validation import CandidateError, load_candidate


def _run_one(candidate, function_name: str, seed: int) -> list[list[float]]:
    objective = FUNCTIONS[function_name]
    rng = random.Random(seed)
    population: list[tuple[float, list[float]]] = []
    trace: list[list[float]] = []
    for _ in range(candidate.config["INITIAL_SAMPLES"]):
        point = [rng.uniform(*DOMAIN) for _ in range(DIMENSION)]
        population.append((objective(point), point))
        trace.append(point)
    population.sort(key=lambda row: row[0])
    population = population[:candidate.config["POPULATION"]]
    while len(trace) < BUDGET:
        scale = max(candidate.config["MIN_SCALE"], candidate.config["STEP_SCALE"] *
                    candidate.config["COOLING"] ** len(trace))
        state = {"population": [point.copy() for _, point in population], "scale": scale, "parent_index": 0}
        parent_index = candidate.select_parent(state, rng)
        if type(parent_index) is not int or not 0 <= parent_index < len(population):
            raise CandidateError("select_parent returned an invalid index")
        state["parent_index"] = parent_index
        if rng.random() < candidate.config["RESTART_RATE"]:
            point = [rng.uniform(*DOMAIN) for _ in range(DIMENSION)]
        else:
            point = candidate.propose(state, rng)
        if type(point) is not list or len(point) != DIMENSION or any(not math.isfinite(v) for v in point):
            raise CandidateError("propose returned an invalid point")
        cost = objective(point)
        population.append((cost, point))
        population.sort(key=lambda row: row[0])
        population = population[:candidate.config["POPULATION"]]
        trace.append(point)
    return trace


def main() -> int:
    if len(sys.argv) != 3:
        return 2
    try:
        source = Path(sys.argv[1]).read_text(encoding="utf-8")
        task_list = json.loads(sys.argv[2])
        if not isinstance(task_list, list) or not all(type(task) is list and len(task) == 2 and task[0] in FUNCTIONS and type(task[1]) is int for task in task_list):
            raise CandidateError("malformed task list")
        candidate = load_candidate(source)
        traces = [{"function": name, "seed": seed, "points": _run_one(candidate, name, seed)} for name, seed in task_list]
        print(json.dumps({"algorithm": candidate.algorithm, "traces": traces}, separators=(",", ":")))
        return 0
    except (CandidateError, OSError, ValueError, ArithmeticError) as exc:
        print(json.dumps({"error": str(exc)}, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
