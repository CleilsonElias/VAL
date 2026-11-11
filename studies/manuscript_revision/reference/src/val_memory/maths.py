"""Small, dependency-free numerical primitives; scores are not truth estimates."""

from __future__ import annotations

import math
from collections.abc import Iterable


def finite(value: float, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def unit_interval(value: float, name: str = "value") -> float:
    result = finite(value, name)
    if not 0 <= result <= 1:
        raise ValueError(f"{name} must be in [0, 1]")
    return result


def positive_int(value: int, name: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < (0 if allow_zero else 1):
        raise ValueError(f"{name} is outside its allowed range")
    return value


def probabilities(values: Iterable[float]) -> tuple[float, ...]:
    p = tuple(finite(x, "probability") for x in values)
    if not p or any(x < 0 for x in p):
        raise ValueError("probabilities must be nonempty and nonnegative")
    total = math.fsum(p)
    if total <= 0 or not math.isfinite(total):
        raise ValueError("probabilities must have a finite positive sum")
    return tuple(x / total for x in p)


def relational_entropy(values: Iterable[float], *, normalized: bool = True) -> float:
    """LLI-CAMS off-diagonal pair score, not Shannon entropy over normalized pairs.

    H_R = -sum_(i != j) p_i p_j log2(p_i p_j)
        = -2 sum_i p_i(1-p_i) log2(p_i).
    Scale by 2 log2(K) when normalized; K=1 has score zero.
    """
    p = probabilities(values)
    if len(p) == 1:
        return 0.0
    result = -2 * math.fsum(x * (1 - x) * math.log2(x) for x in p if x > 0)
    return max(0.0, result / (2 * math.log2(len(p))) if normalized else result)


def normalized_vector(values: Iterable[float]) -> tuple[float, ...]:
    vector = tuple(finite(x, "vector component") for x in values)
    if not vector:
        raise ValueError("vector must be nonempty")
    scale = max(map(abs, vector))
    if scale == 0:
        raise ValueError("vector must have nonzero norm")
    scaled = tuple(x / scale for x in vector)
    norm = math.sqrt(math.fsum(x * x for x in scaled))
    return tuple(x / norm for x in scaled)


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("vector dimensions differ")
    return max(-1.0, min(1.0, math.fsum(a * b for a, b in zip(left, right))))


def sigmoid(value: float) -> float:
    value = finite(value, "sigmoid argument")
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1 + exp_value)

