"""First-order transition matrix over the per-turn action alphabet.
The pre-registered cells: P(sleep|news), P(sleep|sleep)."""

from __future__ import annotations

from collections import defaultdict

ALPHABET = ["bash", "sleep", "news", "web_search", "art", "no_action"]


def action_sequence(events: list[dict]) -> list[str]:
    """One symbol per free-phase model turn, in order."""
    seq = []
    for e in events:
        if e["phase"] != "free":
            continue
        if e["type"] == "ping":
            seq.append("no_action")
        elif e["type"] == "tool_call" and not e["data"].get("parse_error"):
            seq.append(e["data"]["tool"])
    return seq


def transition_counts(seq: list[str]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for a, b in zip(seq, seq[1:]):
        counts[a][b] += 1
    return {k: dict(v) for k, v in counts.items()}


def transition_matrix(seq: list[str]) -> dict[str, dict[str, float]]:
    counts = transition_counts(seq)
    matrix = {}
    for a, row in counts.items():
        total = sum(row.values())
        matrix[a] = {b: n / total for b, n in row.items()}
    return matrix


def p(matrix: dict, given: str, then: str) -> float | None:
    row = matrix.get(given)
    return None if row is None else row.get(then, 0.0)
