"""Strict validator and loader for source-level candidate optimizer modules.

Candidates use real Python source, but only a deliberately tiny pure-computation
subset.  This prevents candidate source from importing, opening files, spawning
processes, using reflection, or touching evaluator state even before OS isolation.
"""
from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any


class CandidateError(ValueError):
    pass


CONFIG: dict[str, tuple[type, float, float]] = {
    "POPULATION": (int, 2, 24), "INITIAL_SAMPLES": (int, 2, 80),
    "STEP_SCALE": (float, 0.01, 8.0), "MIN_SCALE": (float, 0.001, 4.0),
    "COOLING": (float, 0.80, 1.0), "RESTART_RATE": (float, 0.0, 0.70),
    "ELITE_BIAS": (float, 0.0, 1.0),
}
ALGORITHMS = ("gaussian", "coordinate", "cauchy")
_FUNCTIONS = {"select_parent": ("state", "rng"), "propose": ("state", "rng")}
_NAMES = set(CONFIG) | {"ALGORITHM", "state", "rng", "clip", "len", "math", "parent", "scale", "candidate", "coordinate", "value"}
_STATE_KEYS = {"population", "parent_index", "scale"}


@dataclass(frozen=True)
class CandidateModule:
    config: dict[str, Any]
    select_parent: Any
    propose: Any
    algorithm: str


def _literal(node: ast.AST) -> Any:
    if not isinstance(node, ast.Constant) or isinstance(node.value, bool):
        raise CandidateError("configuration values must be primitive literals")
    return node.value


def _validate_tree(tree: ast.Module) -> dict[str, Any]:
    assignments: dict[str, Any] = {}
    functions: dict[str, ast.FunctionDef] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in assignments or name not in {*CONFIG, "ALGORITHM"}:
                raise CandidateError("only one assignment for each declared configuration field is permitted")
            assignments[name] = _literal(node.value)
        elif isinstance(node, ast.FunctionDef):
            if node.name not in _FUNCTIONS or node.name in functions or node.decorator_list or node.returns:
                raise CandidateError("unexpected optimizer function declaration")
            args = [arg.arg for arg in node.args.args]
            if args != list(_FUNCTIONS[node.name]) or node.args.defaults or node.args.kw_defaults or node.args.vararg or node.args.kwarg:
                raise CandidateError("optimizer functions must use the fixed (state, rng) interface")
            functions[node.name] = node
        else:
            raise CandidateError("module may contain only declared constants and optimizer functions")
    if set(assignments) != {*CONFIG, "ALGORITHM"} or set(functions) != set(_FUNCTIONS):
        raise CandidateError("candidate is missing a required constant or function")
    for name, (kind, low, high) in CONFIG.items():
        value = assignments[name]
        if type(value) is not kind or not math.isfinite(float(value)) or not low <= value <= high:
            raise CandidateError(f"invalid {name}")
    if assignments["MIN_SCALE"] > assignments["STEP_SCALE"]:
        raise CandidateError("MIN_SCALE cannot exceed STEP_SCALE")
    if assignments["ALGORITHM"] not in ALGORITHMS:
        raise CandidateError("invalid ALGORITHM")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Lambda, ast.ClassDef,
                             ast.AsyncFunctionDef, ast.With, ast.Try, ast.Raise, ast.Delete, ast.Yield,
                             ast.Await, ast.NamedExpr)):
            raise CandidateError(f"forbidden syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and (node.id not in _NAMES or node.id.startswith("_")):
            raise CandidateError(f"forbidden name: {node.id}")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                raise CandidateError("private/reflection attributes are forbidden")
            valid = (isinstance(node.value, ast.Name) and node.value.id == "rng" and node.attr in {"random", "randrange", "gauss"}) or \
                    (isinstance(node.value, ast.Name) and node.value.id == "math" and node.attr in {"tan", "pi"})
            if not valid:
                raise CandidateError("forbidden attribute access")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id not in {"clip", "len"}:
                    raise CandidateError("forbidden function call")
            elif not isinstance(node.func, ast.Attribute):
                raise CandidateError("forbidden dynamic call")
            if node.keywords:
                raise CandidateError("keyword calls are not supported")
        if isinstance(node, ast.Subscript) and not _valid_subscript(node):
            raise CandidateError("forbidden subscript target")
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    raise CandidateError("attribute assignment is forbidden")
                if isinstance(target, ast.Subscript) and not (isinstance(target.value, ast.Name) and target.value.id == "candidate"):
                    raise CandidateError("only candidate-vector element assignment is permitted")
    return assignments


def _valid_subscript(node: ast.Subscript) -> bool:
    """Allow fixed state keys and numeric/vector indexing, but no object traversal."""
    if isinstance(node.value, ast.Name) and node.value.id == "state":
        return isinstance(node.slice, ast.Constant) and node.slice.value in _STATE_KEYS
    if isinstance(node.value, ast.Name) and node.value.id in {"parent", "candidate"}:
        return isinstance(node.slice, (ast.Name, ast.Slice, ast.Constant))
    # This covers state["population"][state["parent_index"]] and population indexing.
    if isinstance(node.value, ast.Subscript):
        return _valid_subscript(node.value) and isinstance(node.slice, (ast.Name, ast.Slice, ast.Constant, ast.Subscript))
    return False


def _clip(values: list[float]) -> list[float]:
    if type(values) is not list or len(values) != 4:
        raise CandidateError("proposal must be a four-dimensional list")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        raise CandidateError("proposal contains a non-finite value")
    return [max(-5.0, min(5.0, float(value))) for value in values]


def load_candidate(source: str) -> CandidateModule:
    if not (1 <= len(source.encode("utf-8")) <= 12_000):
        raise CandidateError("candidate source size is out of bounds")
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise CandidateError(f"syntax error: {exc.msg}") from exc
    config = _validate_tree(tree)
    safe_math = SimpleNamespace(tan=math.tan, pi=math.pi)
    namespace: dict[str, Any] = {"__builtins__": {}, "clip": _clip, "len": len, "math": safe_math}
    exec(compile(tree, "candidate_optimizer.py", "exec"), namespace, namespace)
    return CandidateModule(config, namespace["select_parent"], namespace["propose"], config["ALGORITHM"])
