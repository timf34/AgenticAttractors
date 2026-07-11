"""Generate the pilot results report: per-session features, per-model
summaries, and the three pre-registered pilot_v1 tests (P1, P3, P5).

Usage: uv run python -m analysis.pilot_report [experiment]
Writes runs/<experiment>/report.json and prints a markdown summary.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from analysis.features import session_features
from analysis.load import iter_session_dirs, load_events
from analysis.stats import bootstrap_ci, permutation_test
from analysis.transitions import action_sequence, transition_counts


def feature_vector(f: dict) -> list[float]:
    """P1's pre-registered per-session vector (see PREDICTIONS.md)."""
    turns = f["n_tool_calls"] + f["n_pings"]
    tc = f["tool_counts"]
    return [
        tc.get("bash", 0) / turns if turns else 0.0,
        tc.get("sleep", 0) / turns if turns else 0.0,
        f["n_pings"] / turns if turns else 0.0,
        f["rest_rate"],
        float(len(f["files_touched"])),
        float(f["identity_append"] + f["identity_revise"]),
        float(f["max_ping_streak"]),
    ]


def collect(experiment: str) -> list[dict]:
    rows = []
    for sd in iter_session_dirs(experiment):
        try:
            events = load_events(sd)
            f = session_features(events)
            f["_session_dir"] = str(sd)
            f["_actions"] = action_sequence(events)
            rows.append(f)
        except Exception as e:
            print(f"SKIP {sd}: {e}", file=sys.stderr)
    return rows


def per_model_summary(rows: list[dict]) -> dict:
    out = {}
    for model in sorted({r["model"] for r in rows}):
        rs = [r for r in rows if r["model"] == model]
        n = len(rs)
        tools = Counter()
        for r in rs:
            tools.update(r["tool_counts"])
        sleep_minutes = [m for r in rs for m in r["sleep_minutes"] if m]
        out[model] = {
            "n_sessions": n,
            "tool_totals": dict(tools),
            "mean_rest_rate": sum(r["rest_rate"] for r in rs) / n,
            "sessions_with_sleep": sum(1 for r in rs if r["n_sleeps"] > 0),
            "mean_sleep_minutes": (sum(sleep_minutes) / len(sleep_minutes))
            if sleep_minutes else 0.0,
            "sessions_touching_identity": sum(
                1 for r in rs if "identity.md" in r["files_touched"]),
            "sessions_touching_diary": sum(
                1 for r in rs if "diary.md" in r["files_touched"]),
            "identity_append_total": sum(r["identity_append"] for r in rs),
            "identity_revise_total": sum(r["identity_revise"] for r in rs),
            "mean_files_touched": sum(len(r["files_touched"]) for r in rs) / n,
            "mean_cost_usd": sum(r["cost_usd"] or 0 for r in rs) / n,
            "end_reasons": dict(Counter(r["end_reason"] for r in rs)),
        }
    return out


def p1_within_between(rows: list[dict]) -> dict:
    models = sorted({r["model"] for r in rows})
    if len(models) != 2:
        return {"error": f"need exactly 2 models, got {models}"}
    a = [feature_vector(r) for r in rows if r["model"] == models[0]]
    b = [feature_vector(r) for r in rows if r["model"] == models[1]]
    result = {"models": models, "pooled_p": permutation_test(a, b)}
    for para in sorted({r["paraphrase"] for r in rows}):
        pa = [feature_vector(r) for r in rows
              if r["model"] == models[0] and r["paraphrase"] == para]
        pb = [feature_vector(r) for r in rows
              if r["model"] == models[1] and r["paraphrase"] == para]
        if len(pa) >= 3 and len(pb) >= 3:
            result[f"p_{para}"] = permutation_test(pa, pb)
    return result


def p3_rest_absorbing(rows: list[dict]) -> dict:
    out = {}
    for model in sorted({r["model"] for r in rows}):
        counts: dict = defaultdict(lambda: defaultdict(int))
        for r in rows:
            if r["model"] != model:
                continue
            tc = transition_counts(r["_actions"])
            for a, row_ in tc.items():
                for b, n in row_.items():
                    counts[a][b] += n
        sleep_row = counts.get("sleep", {})
        total = sum(sleep_row.values())
        out[model] = {
            "p_sleep_given_sleep": (sleep_row.get("sleep", 0) / total)
            if total else None,
            "n_sleep_transitions": total,
            "conclusive": total >= 10,
        }
    return out


def p5_identity_ratchet(rows: list[dict]) -> dict:
    out = {}
    for model in sorted({r["model"] for r in rows}):
        appends = sum(r["identity_append"] for r in rows if r["model"] == model)
        revises = sum(r["identity_revise"] for r in rows if r["model"] == model)
        total = appends + revises
        entry = {"appends": appends, "revises": revises,
                 "deletion_fraction": (revises / total) if total else None}
        if total >= 5:
            flags = [1.0] * appends + [0.0] * revises
            entry["append_fraction_ci95"] = bootstrap_ci(flags)
        out[model] = entry
    return out


def main(experiment: str = "pilot_v1") -> dict:
    rows = collect(experiment)
    if not rows:
        print(f"no sessions found for {experiment}")
        return {}
    report = {
        "experiment": experiment,
        "n_sessions": len(rows),
        "total_cost_usd": round(sum(r["cost_usd"] or 0 for r in rows), 2),
        "per_model": per_model_summary(rows),
        "P1_within_between": p1_within_between(rows),
        "P3_rest_absorbing": p3_rest_absorbing(rows),
        "P5_identity_ratchet": p5_identity_ratchet(rows),
    }
    out_path = Path("runs") / experiment / "report.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
    print(f"\nwritten -> {out_path}", file=sys.stderr)
    return report


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "pilot_v1")
