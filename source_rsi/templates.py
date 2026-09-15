"""Constrained source-program synthesizer used as the local 'AI' proposer.

It analyzes the current source with the trusted validator, then emits a whole
new Python source module and a unified diff. This is code generation/program
synthesis in a small grammar, not an LLM or arbitrary code generator.
"""
from __future__ import annotations

import difflib
import hashlib
import random
from dataclasses import dataclass
from typing import Any

from .trusted.candidate_validation import ALGORITHMS, CONFIG, CandidateError, load_candidate


def source_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def render_source(config: dict[str, Any]) -> str:
    algorithm = config["ALGORITHM"]
    if algorithm == "gaussian":
        proposal = '''def propose(state, rng):
    parent = state["population"][state["parent_index"]]
    scale = state["scale"]
    return clip([value + rng.gauss(0.0, scale) for value in parent])
'''
    elif algorithm == "coordinate":
        proposal = '''def propose(state, rng):
    parent = state["population"][state["parent_index"]]
    scale = state["scale"]
    candidate = parent[:]
    coordinate = rng.randrange(len(parent))
    candidate[coordinate] = candidate[coordinate] + rng.gauss(0.0, scale)
    return clip(candidate)
'''
    elif algorithm == "cauchy":
        proposal = '''def propose(state, rng):
    parent = state["population"][state["parent_index"]]
    scale = state["scale"]
    return clip([value + scale * math.tan(math.pi * (rng.random() - 0.5)) for value in parent])
'''
    else:
        raise CandidateError("cannot render unknown algorithm")
    constants = "\n".join(f"{name} = {config[name]!r}" for name in [*CONFIG, "ALGORITHM"])
    return f'''# Candidate optimizer module. It is data-free source code in a restricted interface.\n{constants}\n\n\ndef select_parent(state, rng):\n    if rng.random() < ELITE_BIAS:\n        return 0\n    return rng.randrange(len(state["population"]))\n\n\n{proposal}'''


@dataclass(frozen=True)
class SourceProposal:
    source: str
    parent_hash: str
    child_hash: str
    changes: dict[str, tuple[Any, Any]]
    kind: str
    diff: str


class SourceMutationAI:
    """Analyzes parent source and synthesizes bounded source mutations."""

    _SIGMA = {"POPULATION": 3.0, "INITIAL_SAMPLES": 8.0, "STEP_SCALE": 0.65,
              "MIN_SCALE": 0.22, "COOLING": 0.025, "RESTART_RATE": 0.12, "ELITE_BIAS": 0.22}

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def analyze(self, parent_source: str) -> dict[str, Any]:
        candidate = load_candidate(parent_source)
        return {**candidate.config, "ALGORITHM": candidate.algorithm}

    def propose(self, parent_source: str, generation: int, count: int) -> list[SourceProposal]:
        if count < 1:
            raise ValueError("candidate count must be positive")
        parent_config = self.analyze(parent_source)
        parent_digest = source_hash(parent_source)
        proposals: list[SourceProposal] = []
        seen = {parent_digest}
        # Always include non-parent algorithm bodies first: source-level structural edits.
        mutation_plan: list[str] = [f"algorithm:{name}" for name in ALGORITHMS if name != parent_config["ALGORITHM"]]
        mutation_plan.extend("mixed" if self.rng.random() < 0.35 else "numeric" for _ in range(count * 4))
        for mode in mutation_plan:
            if len(proposals) >= count:
                break
            child = dict(parent_config)
            changes: dict[str, tuple[Any, Any]] = {}
            if mode.startswith("algorithm:") or mode == "mixed":
                options = [name for name in ALGORITHMS if name != child["ALGORITHM"]]
                value = mode.split(":", 1)[1] if mode.startswith("algorithm:") else self.rng.choice(options)
                changes["ALGORITHM"] = (child["ALGORITHM"], value)
                child["ALGORITHM"] = value
            if mode in {"numeric", "mixed"}:
                field_count = 1 if self.rng.random() < 0.72 else 2
                for field in self.rng.sample(list(CONFIG), field_count):
                    kind, low, high = CONFIG[field]
                    old = child[field]
                    value = max(low, min(high, float(old) + self.rng.gauss(0, self._SIGMA[field])))
                    value = int(round(value)) if kind is int else round(value, 6)
                    child[field] = value
                    if value != old:
                        changes[field] = (old, value)
                if child["MIN_SCALE"] > child["STEP_SCALE"]:
                    changes["MIN_SCALE"] = (parent_config["MIN_SCALE"], child["STEP_SCALE"])
                    child["MIN_SCALE"] = child["STEP_SCALE"]
            if not changes:
                continue
            source = render_source(child)
            child_digest = source_hash(source)
            if child_digest in seen:
                continue
            seen.add(child_digest)
            kind = "algorithmic-source-rewrite" if "ALGORITHM" in changes else "hyperparameter-source-edit"
            diff = "\n".join(difflib.unified_diff(parent_source.splitlines(), source.splitlines(),
                                                   fromfile=f"parent-{parent_digest}.py", tofile=f"child-{child_digest}.py", lineterm=""))
            proposals.append(SourceProposal(source, parent_digest, child_digest, changes, kind, diff))
        if len(proposals) != count:
            raise RuntimeError("synthesizer failed to produce enough distinct source candidates")
        return proposals
