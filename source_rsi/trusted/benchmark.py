"""Fixed benchmark owned by the evaluator, never by candidate source."""
from __future__ import annotations

import math
from typing import Callable

DIMENSION = 4
BUDGET = 240
DOMAIN = (-5.0, 5.0)
TRAIN_SEEDS = (101, 211, 307)
VALIDATION_SEEDS = (809, 907, 1009)
AUDIT_SEEDS = (1511, 1601, 1709)


def sphere(x: list[float]) -> float:
    return sum(v * v for v in x)


def rastrigin(x: list[float]) -> float:
    return 10 * len(x) + sum(v * v - 10 * math.cos(2 * math.pi * v) for v in x)


def ackley(x: list[float]) -> float:
    n = len(x)
    return -20 * math.exp(-0.2 * math.sqrt(sum(v * v for v in x) / n)) - math.exp(
        sum(math.cos(2 * math.pi * v) for v in x) / n
    ) + 20 + math.e


def rosenbrock(x: list[float]) -> float:
    return sum(100 * (x[i + 1] - x[i] ** 2) ** 2 + (1 - x[i]) ** 2 for i in range(len(x) - 1))


FUNCTIONS: dict[str, Callable[[list[float]], float]] = {
    "sphere": sphere, "rastrigin": rastrigin, "ackley": ackley, "rosenbrock": rosenbrock,
}


def tasks(split: str) -> list[tuple[str, int]]:
    seeds = {"train": TRAIN_SEEDS, "validation": VALIDATION_SEEDS, "audit": AUDIT_SEEDS}[split]
    return [(name, seed) for name in FUNCTIONS for seed in seeds]
