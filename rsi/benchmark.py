"""Fixed, candidate-inaccessible objective benchmark."""
from __future__ import annotations

import math
from typing import Callable

DIMENSION = 4
BUDGET = 320
TRAIN_SEEDS = (101, 211, 307, 401, 503, 601, 701)
VALIDATION_SEEDS = (809, 907, 1009, 1103, 1201, 1301, 1409)
AUDIT_SEEDS = (1511, 1601, 1709, 1801, 1901, 2003, 2111)
DOMAIN = (-5.0, 5.0)


def sphere(x: list[float]) -> float:
    return sum(v * v for v in x)


def rastrigin(x: list[float]) -> float:
    return 10 * len(x) + sum(v * v - 10 * math.cos(2 * math.pi * v) for v in x)


def ackley(x: list[float]) -> float:
    n = len(x)
    a = -20 * math.exp(-0.2 * math.sqrt(sum(v * v for v in x) / n))
    b = -math.exp(sum(math.cos(2 * math.pi * v) for v in x) / n)
    return a + b + 20 + math.e


def rosenbrock(x: list[float]) -> float:
    return sum(100 * (x[i + 1] - x[i] ** 2) ** 2 + (1 - x[i]) ** 2 for i in range(len(x) - 1))


FUNCTIONS: tuple[tuple[str, Callable[[list[float]], float]], ...] = (
    ("sphere", sphere), ("rastrigin", rastrigin), ("ackley", ackley), ("rosenbrock", rosenbrock),
)


def split_seeds(split: str) -> tuple[int, ...]:
    mapping = {"train": TRAIN_SEEDS, "validation": VALIDATION_SEEDS, "audit": AUDIT_SEEDS}
    try:
        return mapping[split]
    except KeyError as exc:
        raise ValueError(f"unknown split {split!r}") from exc
