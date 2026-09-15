"""The fixed interpreter for the mutable policy program."""
from __future__ import annotations

import random
import math

from .benchmark import BUDGET, DIMENSION, DOMAIN
from .schema import PolicyProgram


def _clip(point: list[float]) -> list[float]:
    return [max(DOMAIN[0], min(DOMAIN[1], value)) for value in point]


def optimize(policy: PolicyProgram, objective, seed: int) -> tuple[float, int]:
    """Run a bounded population/local-search policy; return best cost and calls."""
    rng = random.Random(seed)
    calls = 0
    population: list[tuple[float, list[float]]] = []

    def assess(point: list[float]) -> None:
        nonlocal calls
        population.append((objective(point), point))
        calls += 1

    for _ in range(min(policy.initial_samples, BUDGET)):
        assess([rng.uniform(*DOMAIN) for _ in range(DIMENSION)])
    population.sort(key=lambda item: item[0])
    population = population[:policy.population]

    while calls < BUDGET:
        progress = calls / BUDGET
        scale = max(policy.min_scale, policy.step_scale * policy.cooling ** (progress * BUDGET))
        if rng.random() < policy.restart_rate:
            candidate = [rng.uniform(*DOMAIN) for _ in range(DIMENSION)]
        else:
            # elite_bias selects the current best more often; the remainder keeps diversity.
            parent_index = 0 if rng.random() < policy.elite_bias else rng.randrange(len(population))
            parent = population[parent_index][1]
            if policy.proposal_kernel == "gaussian":
                candidate = [value + rng.gauss(0.0, scale) for value in parent]
            elif policy.proposal_kernel == "coordinate":
                candidate = parent.copy()
                coordinate = rng.randrange(DIMENSION)
                candidate[coordinate] += rng.gauss(0.0, scale)
            elif policy.proposal_kernel == "cauchy":
                # A heavy-tailed local kernel is a bounded algorithmic choice.
                candidate = [value + scale * math.tan(math.pi * (rng.random() - 0.5)) for value in parent]
            else:  # Validator should make this unreachable; fail closed regardless.
                raise ValueError("unrecognized proposal kernel")
            candidate = _clip(candidate)
        assess(candidate)
        population.sort(key=lambda item: item[0])
        population = population[:policy.population]
    return population[0][0], calls
