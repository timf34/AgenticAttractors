"""Pre-registered statistics (skeleton — implement against pilot data).

Planned:
  - within- vs between-model divergence of per-session feature vectors,
    permutation test on model labels
  - T0 vs T1 total-rest comparison with bootstrap CIs (the headline
    dedicated-sleep-tool prediction)
  - rest self-transition P(sleep|sleep) per model
"""

from __future__ import annotations

import random


def permutation_test(
    group_a: list[list[float]], group_b: list[list[float]],
    n_perm: int = 10_000, seed: int = 0,
) -> float:
    """Two-sample permutation test on the distance between group centroids."""

    def centroid(rows: list[list[float]]) -> list[float]:
        return [sum(col) / len(col) for col in zip(*rows)]

    def dist(u: list[float], v: list[float]) -> float:
        return sum((a - b) ** 2 for a, b in zip(u, v)) ** 0.5

    observed = dist(centroid(group_a), centroid(group_b))
    pooled = group_a + group_b
    n_a = len(group_a)
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(pooled)
        if dist(centroid(pooled[:n_a]), centroid(pooled[n_a:])) >= observed:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def bootstrap_ci(values: list[float], n_boot: int = 10_000,
                 alpha: float = 0.05, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    means = sorted(
        sum(rng.choices(values, k=len(values))) / len(values)
        for _ in range(n_boot)
    )
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[int((1 - alpha / 2) * n_boot)]
    return lo, hi
