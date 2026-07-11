"""Cheap per-session features, pure functions over the event list.
One dict per session; every planned headline statistic starts here."""

from __future__ import annotations

from collections import Counter


def session_features(events: list[dict]) -> dict:
    start = next(e for e in events if e["type"] == "session_start")
    end = next((e for e in events if e["type"] == "session_end"), None)
    calls = [e for e in events if e["type"] == "tool_call" and e["phase"] == "free"]
    results = [e for e in events if e["type"] == "tool_result"]
    sleeps = [e for e in events if e["type"] == "sleep"]
    pings = [e for e in events if e["type"] == "ping"]

    tool_counts = Counter(c["data"]["tool"] for c in calls)
    parse_errors = sum(1 for c in calls if c["data"].get("parse_error"))

    files_touched: set[str] = set()
    identity_revise = identity_append = 0
    bash_sleep_attempts = 0
    for r in results:
        d = r["data"]
        files_touched.update(d.get("files_changed") or [])
        stat = (d.get("diff_stat") or {}).get("identity.md")
        if stat:
            if stat["-"] > 0:
                identity_revise += 1
            else:
                identity_append += 1
        if d.get("tool") == "bash" and d.get("timed_out"):
            bash_sleep_attempts += 1

    totals = (end or {}).get("data", {}).get("totals", {})
    sim_hours = totals.get("sim_hours", 0) or 0
    asleep = totals.get("sim_hours_asleep", 0) or 0

    # consecutive-ping streaks (total-N is the termination rule; streaks are
    # the derived attractor feature)
    streaks, cur = [], 0
    for e in events:
        if e["type"] == "ping":
            cur += 1
        elif e["type"] == "tool_call":
            if cur:
                streaks.append(cur)
            cur = 0
    if cur:
        streaks.append(cur)

    first_sleep = next((i for i, c in enumerate(calls)
                        if c["data"]["tool"] == "sleep"), None)
    first_identity = next(
        (i for i, r in enumerate(results)
         if "identity.md" in (r["data"].get("files_changed") or [])), None)

    return {
        "run_id": start["run_id"],
        "session_idx": start["session_idx"],
        "model": start["data"]["model_key"],
        "paraphrase": start["data"]["paraphrase"],
        "affordance": start["data"]["affordance"],
        "tool_menu": start["data"]["tool_menu"],
        "ping_variant": start["data"]["ping_variant"],
        "seed": start["data"]["seed"],
        "end_reason": (end or {}).get("data", {}).get("end_reason"),
        "n_tool_calls": len(calls),
        "n_pings": len(pings),
        "tool_counts": dict(tool_counts),
        "parse_error_rate": parse_errors / len(calls) if calls else 0.0,
        "rest_rate": asleep / sim_hours if sim_hours else 0.0,
        "sim_hours": sim_hours,
        "sim_hours_asleep": asleep,
        "n_sleeps": len(sleeps),
        "sleep_minutes": [s["data"].get("granted_minutes") for s in sleeps],
        "bash_sleep_attempts": bash_sleep_attempts,
        "files_touched": sorted(files_touched),
        "identity_revise": identity_revise,
        "identity_append": identity_append,
        "ping_streaks": streaks,
        "max_ping_streak": max(streaks, default=0),
        "first_sleep_call_idx": first_sleep,
        "first_identity_edit_idx": first_identity,
        "cost_usd": totals.get("cost_usd"),
    }
