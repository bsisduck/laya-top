"""Small pure helpers shared by performance tools and their unit tests."""

import math
import statistics
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def duration(callable_: Callable[[], T]) -> tuple[T, float]:
    started = time.perf_counter()
    result = callable_()
    return result, time.perf_counter() - started


def summary(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    p95_index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return {
        "minimum_ms": round(ordered[0] * 1000, 3),
        "median_ms": round(statistics.median(ordered) * 1000, 3),
        "p95_ms": round(ordered[p95_index] * 1000, 3),
        "maximum_ms": round(ordered[-1] * 1000, 3),
    }
