"""Local proposal generator. Replaceable by a validated structured-LLM adapter."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .schema import CHOICE_FIELDS, FIELDS, PolicyProgram, policy_from_dict


@dataclass(frozen=True)
class Proposal:
    policy: PolicyProgram
    changed: dict[str, tuple[object, object]]
    source: str


class MutationGenerator:
    """A bounded evolutionary generator; it cannot write or execute source code."""

    # Relative mutation sizes deliberately span conservative and exploratory moves.
    _SIGMA = {
        "population": 3.0, "initial_samples": 8.0, "step_scale": 0.65,
        "min_scale": 0.22, "cooling": 0.025, "restart_rate": 0.12, "elite_bias": 0.22,
    }

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def propose(self, parent: PolicyProgram, generation: int, count: int) -> list[Proposal]:
        if count < 1:
            raise ValueError("candidate count must be positive")
        proposals: list[Proposal] = []
        seen = {parent.digest()}
        attempts = 0
        while len(proposals) < count and attempts < count * 30:
            attempts += 1
            field_count = 1 if self.rng.random() < 0.72 else 2
            fields = self.rng.sample([*FIELDS, *CHOICE_FIELDS], field_count)
            raw = parent.canonical()
            changes: dict[str, tuple[object, object]] = {}
            for field in fields:
                if field in CHOICE_FIELDS:
                    old = raw[field]
                    value = self.rng.choice([choice for choice in CHOICE_FIELDS[field] if choice != old])
                    raw[field] = value
                    changes[field] = (old, value)
                    continue
                typ, low, high = FIELDS[field]
                old = raw[field]
                proposed = max(low, min(high, float(old) + self.rng.gauss(0, self._SIGMA[field])))
                value = int(round(proposed)) if typ is int else round(proposed, 6)
                raw[field] = value
                if value != old:
                    changes[field] = (old, value)
            # Preserve cross-field invariant deterministically.
            if raw["min_scale"] > raw["step_scale"]:
                raw["min_scale"] = raw["step_scale"]
                changes["min_scale"] = (parent.min_scale, raw["min_scale"])
            if not changes:
                continue
            raw["name"] = f"g{generation}-m{len(proposals):02d}"
            try:
                candidate = policy_from_dict(raw)
            except ValueError:
                continue
            if candidate.digest() not in seen:
                seen.add(candidate.digest())
                proposals.append(Proposal(candidate, changes, "bounded-random-mutation"))
        if len(proposals) != count:
            raise RuntimeError("could not produce the requested number of distinct policies")
        return proposals
