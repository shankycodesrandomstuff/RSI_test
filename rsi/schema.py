"""The entire mutable program grammar and its validation boundary."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
FIELDS: dict[str, tuple[type, float, float]] = {
    "population": (int, 2, 24),
    "initial_samples": (int, 2, 80),
    "step_scale": (float, 0.01, 8.0),
    "min_scale": (float, 0.001, 4.0),
    "cooling": (float, 0.80, 1.0),
    "restart_rate": (float, 0.0, 0.70),
    "elite_bias": (float, 0.0, 1.0),
}
# These alter the interpreted search algorithm, while remaining finite choices
# in a data-only grammar rather than arbitrary code supplied by a candidate.
CHOICE_FIELDS: dict[str, tuple[str, ...]] = {
    "proposal_kernel": ("gaussian", "coordinate", "cauchy"),
}
REQUIRED_KEYS = {"schema_version", "name", *FIELDS, *CHOICE_FIELDS}


class PolicyError(ValueError):
    """A candidate did not belong to the policy DSL."""


@dataclass(frozen=True)
class PolicyProgram:
    """A data-only search program. No candidate text is executed as code."""

    schema_version: int
    name: str
    population: int
    initial_samples: int
    step_scale: float
    min_scale: float
    cooling: float
    restart_rate: float
    elite_bias: float
    proposal_kernel: str

    def canonical(self) -> dict[str, Any]:
        return asdict(self)

    def digest(self) -> str:
        encoded = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]

    def to_json(self, path: Path) -> None:
        path.write_text(json.dumps(self.canonical(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def policy_from_dict(data: Any) -> PolicyProgram:
    if not isinstance(data, dict) or set(data) != REQUIRED_KEYS:
        raise PolicyError("candidate must contain exactly the policy DSL fields")
    if data["schema_version"] != SCHEMA_VERSION:
        raise PolicyError("unsupported schema version")
    name = data["name"]
    if not isinstance(name, str) or not (1 <= len(name) <= 80):
        raise PolicyError("name must be a 1..80 character string")
    if any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for ch in name):
        raise PolicyError("name contains unsupported characters")
    parsed: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "name": name}
    for field, (typ, low, high) in FIELDS.items():
        value = data[field]
        # bool is a subclass of int and must not enter the program grammar.
        if type(value) is not typ or not math.isfinite(float(value)) or not low <= value <= high:
            raise PolicyError(f"{field} must be a finite {typ.__name__} in [{low}, {high}]")
        parsed[field] = value
    for field, choices in CHOICE_FIELDS.items():
        if data[field] not in choices:
            raise PolicyError(f"{field} must be one of {choices}")
        parsed[field] = data[field]
    if parsed["min_scale"] > parsed["step_scale"]:
        raise PolicyError("min_scale cannot exceed step_scale")
    return PolicyProgram(**parsed)


def load_policy(path: Path) -> PolicyProgram:
    try:
        return policy_from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError(f"cannot load policy: {exc}") from exc


def safe_child(root: Path, *parts: str) -> Path:
    """Return a path only if it remains within the canonical output root."""
    base = root.resolve()
    result = base.joinpath(*parts).resolve()
    if result != base and base not in result.parents:
        raise PolicyError("attempted path escape from experiment output")
    return result
